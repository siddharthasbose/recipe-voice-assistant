import json
import logging
import google.generativeai as genai
from typing import Dict, Any, Optional
import traceback
import re

logger = logging.getLogger(__name__)

class NutritionAnalyzer:
    def __init__(self, model):
        self.model = model
        logger.info("NutritionAnalyzer initialized with Gemini model")

    def analyze_recipe(self, recipe_description: str) -> Optional[Dict[str, Any]]:
        """
        Analyze recipe description and return structured nutrition information.
        """
        logger.info(f"Starting nutrition analysis for recipe: {recipe_description[:100]}...")
        
        prompt = f"""
        Analyze this recipe and provide nutritional information in a structured format.
        Recipe: {recipe_description}

        Return ONLY a JSON object in this exact format:
        {{
            "nutrition": {{
                "calories": number,
                "protein": number,
                "carbs": number,
                "fat": number
            }},
            "confidence": {{
                "calories": number between 0-1,
                "protein": number between 0-1,
                "carbs": number between 0-1,
                "fat": number between 0-1
            }},
            "serving_size": {{
                "amount": number,
                "unit": "g" or "ml" or "oz" or "cup"
            }},
            "notes": [
                "List of assumptions made",
                "Key ingredients considered",
                "Any limitations in the analysis"
            ]
        }}

        Rules:
        1. All numbers must be integers or floats
        2. Confidence scores must be between 0 and 1
        3. Only include the JSON object, no other text
        4. If you can't determine a value, use null
        5. Base estimates on standard portion sizes
        6. Consider cooking methods and their impact on nutrition
        """

        try:
            logger.info("Sending prompt to Gemini for nutrition analysis")
            # Get response from Gemini
            response = self.model.generate_content(prompt)
            logger.info(f"Received response from Gemini: {response.text[:200]}...")
            
            # Clean the response text by removing markdown formatting and extra data
            cleaned_text = response.text
            if cleaned_text.startswith('```json'):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.endswith('```'):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip()
            
            # Extract just the JSON object using regex
            json_match = re.search(r'\{[\s\S]*\}', cleaned_text)
            if json_match:
                cleaned_text = json_match.group()
            
            logger.info(f"Cleaned response text: {cleaned_text[:200]}...")
            
            # Parse the response as JSON
            try:
                nutrition_data = json.loads(cleaned_text)
                logger.info("Successfully parsed Gemini response as JSON")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Gemini response as JSON: {str(e)}")
                logger.error(f"Raw response: {response.text}")
                return None
            
            # Validate the structure
            required_fields = ['nutrition', 'confidence', 'serving_size', 'notes']
            for field in required_fields:
                if field not in nutrition_data:
                    logger.error(f"Missing required field in nutrition data: {field}")
                    logger.error(f"Available fields: {list(nutrition_data.keys())}")
                    return None

            # Validate nutrition values
            nutrition = nutrition_data['nutrition']
            logger.info("Validating nutrition values")
            for nutrient in ['calories', 'protein', 'carbs', 'fat']:
                if nutrition.get(nutrient) is not None:
                    try:
                        nutrition[nutrient] = float(nutrition[nutrient])
                        logger.info(f"Validated {nutrient}: {nutrition[nutrient]}")
                    except (ValueError, TypeError) as e:
                        logger.error(f"Invalid nutrition value for {nutrient}: {nutrition.get(nutrient)}")
                        logger.error(f"Error: {str(e)}")
                        return None

            # Validate confidence scores
            confidence = nutrition_data['confidence']
            logger.info("Validating confidence scores")
            for nutrient in ['calories', 'protein', 'carbs', 'fat']:
                if confidence.get(nutrient) is not None:
                    try:
                        conf_value = float(confidence[nutrient])
                        if not 0 <= conf_value <= 1:
                            logger.error(f"Confidence score for {nutrient} out of range: {conf_value}")
                            return None
                        confidence[nutrient] = conf_value
                        logger.info(f"Validated confidence for {nutrient}: {conf_value}")
                    except (ValueError, TypeError) as e:
                        logger.error(f"Invalid confidence score for {nutrient}: {confidence.get(nutrient)}")
                        logger.error(f"Error: {str(e)}")
                        return None

            logger.info("Nutrition analysis completed successfully")
            logger.info(f"Final nutrition data: {json.dumps(nutrition_data, indent=2)}")
            return nutrition_data

        except Exception as e:
            logger.error(f"Error in nutrition analysis: {str(e)}")
            logger.error(f"Full error details: {traceback.format_exc()}")
            return None 