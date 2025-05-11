from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import requests
import os
import json
import logging
import traceback
from dotenv import load_dotenv
from recipe_sources import RecipeSource

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configure Google API
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    logger.error("GOOGLE_API_KEY not found in environment variables")
    raise ValueError("GOOGLE_API_KEY environment variable is required")

# Configure Gemini
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Initialize recipe sources
recipe_source = RecipeSource()

@app.route('/extract_context', methods=['POST'])
def extract_context():
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            logger.error("No text provided in request")
            return jsonify({'error': 'No text provided'}), 400

        text = data.get('text', '').lower()  # Convert to lowercase for easier matching
        previous_context = data.get('previous_context')
        clarification_count = data.get('clarification_count', 0)
        MAX_CLARIFICATIONS = 3

        logger.info(f"Received text for context extraction: {text}")
        if previous_context:
            logger.info(f"Previous context: {previous_context}")
        logger.info(f"Clarification count: {clarification_count}")

        # If we've reached max clarifications, use defaults for missing fields
        if clarification_count >= MAX_CLARIFICATIONS:
            logger.info("Maximum clarifications reached, using defaults for missing fields")
            context = previous_context or {}
            for key in ['diet_type', 'cuisine', 'dish_attributes']:
                if not context.get(key) or context[key] == 'null':
                    context[key] = 'any'
            context['clarifying_questions'] = []
            return jsonify(context)

        # Create a prompt for Gemini based on whether this is a follow-up
        if previous_context:
            prompt = f"""
            Previous context:
            - Diet type: {previous_context.get('diet_type')}
            - Cuisine: {previous_context.get('cuisine')}
            - Dish attributes: {previous_context.get('dish_attributes')}

            User's response to clarifying questions: "{text}"

            Extract the following information and return it in JSON format:
            {{
                "diet_type": "vegetarian", "vegan", "non-veg", or null,
                "cuisine": specific cuisine or null,
                "dish_attributes": specific attributes or null,
                "clarifying_questions": [
                    "question for missing field 1",
                    "question for missing field 2"
                ]
            }}

            Rules:
            1. Keep all previously provided values unless explicitly changed
            2. Only ask clarifying questions for fields that are still unclear
            3. If the user provides new information, update only those specific fields
            4. If a field is still unclear, set it to null and add a clarifying question
            5. If the user says "any", "no preference", or similar, set that field to "any"
            """
        else:
            prompt = f"""
            Extract the following information from this recipe request: "{text}"
            - diet_type (vegetarian, vegan, or non-veg)
            - cuisine (e.g., Indian, Chinese, Italian, etc.)
            - dish_attributes (specific characteristics or preferences)

            Return the information in this JSON format:
            {{
                "diet_type": "vegetarian", "vegan", "non-veg", or null,
                "cuisine": specific cuisine or null,
                "dish_attributes": specific attributes or null,
                "clarifying_questions": [
                    "question for missing field 1",
                    "question for missing field 2"
                ]
            }}

            Rules:
            1. Only ask clarifying questions if absolutely necessary
            2. If you understand any preference, use it
            3. If a field is unclear, set it to null and add a clarifying question
            4. If the user says "any", "no preference", or similar, set that field to "any"
            """

        # Get response from Gemini
        response = model.generate_content(prompt)
        response_text = response.text
        logger.info(f"Received response from Gemini: {response_text}")
        
        # Parse the response text as JSON
        try:
            # First try to parse the response directly
            context = json.loads(response_text)
            logger.info("Successfully parsed Gemini response as JSON")
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse response directly: {e}")
            # If that fails, try to extract JSON from the text
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                context = json.loads(json_match.group())
                logger.info("Successfully extracted and parsed JSON from response")
            else:
                logger.error("Could not find JSON in response")
                raise Exception("Could not parse Gemini response as JSON")

        # Convert string 'null' to actual null
        for key in ['diet_type', 'cuisine', 'dish_attributes']:
            if context.get(key) == 'null':
                context[key] = None

        # Handle "no preference" responses
        no_preference_phrases = ['no preference', 'any', 'anything', 'whatever', 'doesn\'t matter']
        for key in ['diet_type', 'cuisine', 'dish_attributes']:
            if context.get(key) and context[key].lower() in no_preference_phrases:
                context[key] = 'any'
                logger.info(f"Setting {key} to 'any' based on user response")

        # Modified context merging logic
        if previous_context:
            logger.info(f"Merging with previous context: {previous_context}")
            # Keep non-null values from previous context
            for key in ['diet_type', 'cuisine', 'dish_attributes']:
                if context.get(key) is None and previous_context.get(key) is not None:
                    context[key] = previous_context[key]
                    logger.info(f"Keeping previous value for {key}: {previous_context[key]}")
                elif context.get(key) is not None:
                    logger.info(f"Using new value for {key}: {context[key]}")

            # Only ask clarifying questions for fields that are still null
            clarifying_questions = []
            if not context.get('diet_type'):
                clarifying_questions.append("What kind of diet are you following (vegetarian, vegan, or non-vegetarian)?")
            if not context.get('cuisine'):
                clarifying_questions.append("What type of cuisine are you interested in?")
            if not context.get('dish_attributes'):
                clarifying_questions.append("Do you have any specific preferences for the dish (e.g., spicy, creamy, quick to make)?")
            
            # Only update clarifying questions if we still have missing fields
            if clarifying_questions:
                context['clarifying_questions'] = clarifying_questions
            else:
                context['clarifying_questions'] = []
                logger.info("All fields filled, no more clarifying questions needed")
        else:
            # For initial request, use the clarifying questions from Gemini
            if not context.get('clarifying_questions'):
                context['clarifying_questions'] = []
                for key in ['diet_type', 'cuisine', 'dish_attributes']:
                    if not context.get(key):
                        if key == 'diet_type':
                            context['clarifying_questions'].append("What kind of diet are you following (vegetarian, vegan, or non-vegetarian)?")
                        elif key == 'cuisine':
                            context['clarifying_questions'].append("What type of cuisine are you interested in?")
                        elif key == 'dish_attributes':
                            context['clarifying_questions'].append("Do you have any specific preferences for the dish (e.g., spicy, creamy, quick to make)?")

        # Ensure all required fields exist
        for key in ['diet_type', 'cuisine', 'dish_attributes']:
            if not context.get(key):  # This catches None and empty string
                context[key] = 'any'
        context.setdefault('clarifying_questions', [])
        
        logger.info(f"Final context object: {context}")
        return jsonify(context)

    except Exception as e:
        error_msg = f"Error in extract_context: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return jsonify({'error': str(e)}), 500

@app.route('/get_recipes', methods=['POST'])
def get_recipes():
    try:
        data = request.get_json()
        if not data:
            logger.error("No data provided in request")
            return jsonify({'error': 'No data provided'}), 400

        logger.info(f"Received recipe request with data: {data}")
        
        # Get recipes from all available sources
        recipes = recipe_source.get_all_recipes(data)
        logger.info(f"Retrieved {len(recipes)} recipes from all sources")
        
        return jsonify(recipes)

    except Exception as e:
        error_msg = f"Error in get_recipes: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 