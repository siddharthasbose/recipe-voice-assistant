import os
import requests
import json
import logging
import google.generativeai as genai
from typing import List, Dict, Any
from bs4 import BeautifulSoup
import feedparser
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

class RecipeSource:
    def __init__(self):
        self.spoonacular_api_key = os.getenv('SPOONACULAR_API_KEY')
        self.youtube_api_key = os.getenv('YOUTUBE_API_KEY')
        self.google_api_key = os.getenv('GOOGLE_API_KEY')
        
        if not self.spoonacular_api_key:
            logger.warning("SPOONACULAR_API_KEY not found")
        if not self.youtube_api_key:
            logger.warning("YOUTUBE_API_KEY not found")
        if not self.google_api_key:
            logger.warning("GOOGLE_API_KEY not found")
            raise ValueError("GOOGLE_API_KEY is required")

        # Configure Gemini
        genai.configure(api_key=self.google_api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')

        # Initialize YouTube API client
        if self.youtube_api_key:
            self.youtube = build('youtube', 'v3', developerKey=self.youtube_api_key)
        
        # Headers to mimic a browser
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }

    def get_all_recipes(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get recipes from all available sources"""
        logger.info(f"Getting recipes for context: {context}")
        recipes = []
        
        # Get recipes from Spoonacular
        if self.spoonacular_api_key:
            logger.info("Fetching recipes from Spoonacular")
            spoonacular_recipes = self._get_spoonacular_recipes(context)
            recipes.extend(spoonacular_recipes)
        
        # Get recipes from YouTube
        if self.youtube_api_key:
            logger.info("Fetching recipes from YouTube")
            youtube_recipes = self._get_youtube_recipes(context)
            recipes.extend(youtube_recipes)
        
        # Get recipes from blogs
        logger.info("Fetching recipes from blogs")
        blog_recipes = self._get_blog_recipes(context)
        recipes.extend(blog_recipes)
        
        logger.info(f"Total recipes found: {len(recipes)}")
        return recipes

    def _get_spoonacular_recipes(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get recipes from Spoonacular API"""
        try:
            # Build query parameters
            params = {
                'apiKey': self.spoonacular_api_key,
                'number': 3,  # Limit to 3 recipes
                'addRecipeNutrition': True,
                'fillIngredients': True,
                'instructionsRequired': True
            }
            
            # Add context-based parameters
            if context.get('diet_type') and context['diet_type'] != 'any':
                params['diet'] = context['diet_type']
            if context.get('cuisine') and context['cuisine'] != 'any':
                params['cuisine'] = context['cuisine']
            if context.get('dish_attributes') and context['dish_attributes'] != 'any':
                params['query'] = context['dish_attributes']
            
            # Make API request
            response = requests.get(
                'https://api.spoonacular.com/recipes/complexSearch',
                params=params
            )
            response.raise_for_status()
            
            data = response.json()
            recipes = []
            
            for recipe in data.get('results', []):
                # Get detailed recipe information
                recipe_id = recipe['id']
                details_response = requests.get(
                    f'https://api.spoonacular.com/recipes/{recipe_id}/information',
                    params={'apiKey': self.spoonacular_api_key}
                )
                details_response.raise_for_status()
                details = details_response.json()
                
                # Extract nutrition information
                nutrition = details.get('nutrition', {})
                nutrients = nutrition.get('nutrients', [])
                nutrition_info = {
                    'calories': next((n['amount'] for n in nutrients if n['name'] == 'Calories'), None),
                    'protein': next((n['amount'] for n in nutrients if n['name'] == 'Protein'), None),
                    'carbs': next((n['amount'] for n in nutrients if n['name'] == 'Carbohydrates'), None),
                    'fat': next((n['amount'] for n in nutrients if n['name'] == 'Fat'), None)
                }
                
                recipes.append({
                    'title': recipe['title'],
                    'sourceUrl': recipe['sourceUrl'],
                    'imageUrl': recipe['image'],
                    'nutrition': nutrition_info,
                    'source': 'Spoonacular'
                })
            
            return recipes
            
        except Exception as e:
            logger.error(f"Error fetching recipes from Spoonacular: {str(e)}")
            return []

    def _get_youtube_recipes(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get recipes from YouTube"""
        try:
            youtube = build('youtube', 'v3', developerKey=self.youtube_api_key)
            
            # Build search query
            query_parts = []
            if context.get('cuisine') and context['cuisine'] != 'any':
                query_parts.append(context['cuisine'])
            if context.get('diet_type') and context['diet_type'] != 'any':
                query_parts.append(context['diet_type'])
            if context.get('dish_attributes') and context['dish_attributes'] != 'any':
                query_parts.append(context['dish_attributes'])
            query_parts.append('recipe')
            
            search_query = ' '.join(query_parts)
            
            # Search for videos
            request = youtube.search().list(
                part='snippet',
                q=search_query,
                type='video',
                maxResults=3,
                relevanceLanguage='en'
            )
            response = request.execute()
            
            recipes = []
            for item in response.get('items', []):
                video_id = item['id']['videoId']
                video_details = youtube.videos().list(
                    part='snippet,contentDetails',
                    id=video_id
                ).execute()
                
                video_info = video_details['items'][0]['snippet']
                
                # Get nutrition information using Gemini
                nutrition_info = self._analyze_recipe_nutrition(video_info['description'])
                
                recipes.append({
                    'title': video_info['title'],
                    'sourceUrl': f'https://www.youtube.com/watch?v={video_id}',
                    'imageUrl': video_info['thumbnails']['high']['url'],
                    'nutrition': nutrition_info.get('nutrition'),
                    'nutrition_confidence': nutrition_info.get('confidence'),
                    'serving_size': nutrition_info.get('serving_size'),
                    'nutrition_notes': nutrition_info.get('notes'),
                    'source': 'YouTube'
                })
            
            return recipes
            
        except Exception as e:
            logger.error(f"Error fetching recipes from YouTube: {str(e)}")
            return []

    def _get_blog_recipes(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get recipes from food blogs"""
        try:
            # Build search query
            query_parts = []
            if context.get('cuisine') and context['cuisine'] != 'any':
                query_parts.append(context['cuisine'])
            if context.get('diet_type') and context['diet_type'] != 'any':
                query_parts.append(context['diet_type'])
            if context.get('dish_attributes') and context['dish_attributes'] != 'any':
                query_parts.append(context['dish_attributes'])
            query_parts.append('recipe')
            
            search_query = ' '.join(query_parts)
            
            # Use Gemini to search and analyze blog recipes
            prompt = f"""
            Find 3 recipes matching: {search_query}. For each recipe, provide the title, URL, and a brief description. Return the results in JSON format.
            """
            
            response = self.model.generate_content(prompt)
            response_text = response.text
            
            # Parse the response
            try:
                recipes_data = json.loads(response_text)
                recipes = []
                
                for recipe in recipes_data:
                    # Get nutrition information using Gemini
                    nutrition_info = self._analyze_recipe_nutrition(recipe.get('description', ''))
                    
                    recipes.append({
                        'title': recipe['title'],
                        'sourceUrl': recipe['url'],
                        'nutrition': nutrition_info.get('nutrition'),
                        'nutrition_confidence': nutrition_info.get('confidence'),
                        'serving_size': nutrition_info.get('serving_size'),
                        'nutrition_notes': nutrition_info.get('notes'),
                        'source': 'Blog'
                    })
                
                return recipes
                
            except json.JSONDecodeError:
                logger.error("Failed to parse Gemini response for blog recipes")
                return []
            
        except Exception as e:
            logger.error(f"Error fetching recipes from blogs: {str(e)}")
            return []

    def _analyze_recipe_nutrition(self, recipe_text: str) -> Dict[str, Any]:
        """Analyze recipe nutrition using Gemini"""
        try:
            logger.info(f"Starting nutrition analysis for recipe: {recipe_text[:100]}...")
            
            prompt = f"""
            Analyze the nutritional content of this recipe:
            {recipe_text}

            Return the analysis in this JSON format:
            {{
                "nutrition": {{
                    "calories": number or null,
                    "protein": number or null,
                    "carbs": number or null,
                    "fat": number or null
                }},
                "confidence": {{
                    "calories": number between 0 and 1,
                    "protein": number between 0 and 1,
                    "carbs": number between 0 and 1,
                    "fat": number between 0 and 1
                }},
                "serving_size": {{
                    "amount": number or null,
                    "unit": string or null
                }},
                "notes": [
                    "note about the analysis",
                    "note about assumptions",
                    "note about limitations"
                ]
            }}

            Rules:
            1. If you can't determine a value, use null
            2. Confidence scores should reflect your certainty (0 = completely uncertain, 1 = completely certain)
            3. Include notes about any assumptions or limitations
            4. Be conservative in your estimates
            """

            logger.info("Sending prompt to Gemini for nutrition analysis")
            response = self.model.generate_content(prompt)
            response_text = response.text
            logger.info(f"Received response from Gemini: {response_text}")
            
            # Clean the response text
            cleaned_text = response_text.replace('```json', '').replace('```', '').strip()
            logger.info(f"Cleaned response text: {cleaned_text}")
            
            # Parse the JSON response
            try:
                nutrition_data = json.loads(cleaned_text)
                logger.info("Successfully parsed Gemini response as JSON")
                
                # Validate nutrition values
                logger.info("Validating nutrition values")
                for key, value in nutrition_data.get('nutrition', {}).items():
                    if value is not None:
                        nutrition_data['nutrition'][key] = float(value)
                        logger.info(f"Validated {key}: {value}")
                
                # Validate confidence scores
                logger.info("Validating confidence scores")
                for key, value in nutrition_data.get('confidence', {}).items():
                    if value is not None:
                        nutrition_data['confidence'][key] = float(value)
                        logger.info(f"Validated confidence for {key}: {value}")
                
                logger.info("Nutrition analysis completed successfully")
                logger.info(f"Final nutrition data: {json.dumps(nutrition_data, indent=2)}")
                return nutrition_data
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse nutrition data: {str(e)}")
                return {
                    'nutrition': {'calories': None, 'protein': None, 'carbs': None, 'fat': None},
                    'confidence': {'calories': 0, 'protein': 0, 'carbs': 0, 'fat': 0},
                    'serving_size': {'amount': None, 'unit': None},
                    'notes': ['Failed to analyze nutrition information']
                }
                
        except Exception as e:
            logger.error(f"Error in nutrition analysis: {str(e)}")
            return {
                'nutrition': {'calories': None, 'protein': None, 'carbs': None, 'fat': None},
                'confidence': {'calories': 0, 'protein': 0, 'carbs': 0, 'fat': 0},
                'serving_size': {'amount': None, 'unit': None},
                'notes': ['Error occurred during nutrition analysis']
            } 