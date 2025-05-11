import { useState, useEffect } from 'react'
import { MicrophoneIcon, StopIcon } from '@heroicons/react/24/solid'

// Add TypeScript definitions for Web Speech API
declare global {
  interface Window {
    SpeechRecognition: typeof SpeechRecognition;
    webkitSpeechRecognition: typeof SpeechRecognition;
  }
}

interface Recipe {
  title: string;
  description: string;
  url: string;
  nutrition: {
    calories: number;
    protein: number;
    carbs: number;
    fat: number;
  };
  imageUrl?: string;
  source: string;
  audio_response?: string;
}

interface Context {
  diet_type: string | null;
  cuisine: string | null;
  dish_attributes: string | null;
  clarifying_questions: string[];
  audio_response?: string;
}

function App() {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [context, setContext] = useState<Context | null>(null);
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isClarifying, setIsClarifying] = useState(false);
  const [clarificationCount, setClarificationCount] = useState(0);
  const MAX_CLARIFICATIONS = 3; // Maximum number of clarifying questions before defaulting
  const [recognition, setRecognition] = useState<SpeechRecognition | null>(null);

  useEffect(() => {
    // Initialize speech recognition
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      console.log('Speech recognition is supported');
      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = false;
      recognition.lang = 'en-US'; // Set language to English

      recognition.onstart = () => {
        console.log('Speech recognition started');
      };

      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        console.log('Speech recognized:', transcript);
        setTranscript(transcript);
        if (isClarifying) {
          console.log('In clarifying mode, using transcript as is');
          extractContext(transcript);
        } else {
          console.log('Starting new context extraction');
          extractContext(transcript);
        }
      };

      recognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        setError('Error occurred in recognition: ' + event.error);
        setIsListening(false);
      };

      recognition.onend = () => {
        console.log('Speech recognition ended');
        setIsListening(false);
      };

      setRecognition(recognition);
    } else {
      console.error('Speech recognition is not supported in this browser');
      setError('Speech recognition is not supported in your browser');
    }
  }, []);

  const playAudio = (audioBase64: string) => {
    const audio = new Audio(`data:audio/mp3;base64,${audioBase64}`);
    audio.play();
  };

  const handleClarificationResponse = async (response: string) => {
    try {
      const result = await extractContext(response, context, clarificationCount);
      setContext(result);
      setClarificationCount(prev => prev + 1);
      
      // Speak the first clarifying question if available
      if (result.clarifying_questions && result.clarifying_questions.length > 0 && clarificationCount < MAX_CLARIFICATIONS) {
        speakText(result.clarifying_questions[0]);
        setIsClarifying(true);
      } else {
        setIsClarifying(false);
        const recipes = await getRecipes(result);
        setRecipes(recipes);
        
        // Announce the number of recipes found
        if (recipes.length > 0) {
          speakText(`I found ${recipes.length} recipes for you. Here they are.`);
        }
      }
    } catch (error) {
      setError('Error processing clarification response');
      console.error('Error:', error);
    }
  };

  const speakText = (text: string) => {
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'en-US';
    window.speechSynthesis.speak(utterance);
  };

  const startListening = () => {
    setIsListening(true);
    setError(null);

    const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    recognition.onresult = async (event) => {
      const transcript = event.results[0][0].transcript;
      setTranscript(transcript);
      setIsListening(false);

      if (isClarifying) {
        await handleClarificationResponse(transcript);
      } else {
        await extractContext(transcript);
      }
    };

    recognition.onerror = (event) => {
      console.error('Speech recognition error:', event.error);
      setError(`Error: ${event.error}`);
      setIsListening(false);
    };

    recognition.start();
  };

  const extractContext = async (text: string, previousContext?: Context | null, clarificationCount: number = 0) => {
    try {
      const response = await fetch('http://localhost:5000/extract_context', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          text,
          previous_context: previousContext,
          clarification_count: clarificationCount
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to extract context');
      }

      const result = await response.json();
      setContext(result);
      
      // Speak the first clarifying question if available
      if (result.clarifying_questions && result.clarifying_questions.length > 0) {
        speakText(result.clarifying_questions[0]);
        setIsClarifying(true);
      } else {
        setIsClarifying(false);
        const recipes = await getRecipes(result);
        setRecipes(recipes);
        
        // Announce the number of recipes found
        if (recipes.length > 0) {
          speakText(`I found ${recipes.length} recipes for you. Here they are.`);
        }
      }

      return result;
    } catch (error) {
      setError('Error extracting context');
      console.error('Error:', error);
      throw error;
    }
  };

  const getRecipes = async (context: Context): Promise<Recipe[]> => {
    try {
      const response = await fetch('http://localhost:5000/get_recipes', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(context),
      });

      if (!response.ok) {
        throw new Error('Failed to fetch recipes');
      }

      const data = await response.json();
      console.log('Recipes received:', data);
      return data;
    } catch (err) {
      console.error('Error fetching recipes:', err);
      setError(`Error fetching recipes: ${err instanceof Error ? err.message : String(err)}`);
      return [];
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 py-6 flex flex-col justify-center sm:py-12">
      <div className="relative py-3 sm:max-w-xl sm:mx-auto">
        <div className="relative px-4 py-10 bg-white shadow-lg sm:rounded-3xl sm:p-20">
          <div className="max-w-md mx-auto">
            <div className="divide-y divide-gray-200">
              <div className="py-8 text-base leading-6 space-y-4 text-gray-700 sm:text-lg sm:leading-7">
                <h1 className="text-3xl font-bold text-center mb-8">Recipe Voice Assistant</h1>
                
                <div className="flex justify-center mb-8">
                  <button
                    onClick={isListening ? startListening : startListening}
                    className={`flex items-center px-4 py-2 rounded-full ${
                      isListening 
                        ? 'bg-red-500 hover:bg-red-600' 
                        : 'bg-blue-500 hover:bg-blue-600'
                    } text-white transition-colors`}
                  >
                    {isListening ? (
                      <>
                        <StopIcon className="h-5 w-5 mr-2" />
                        Stop Listening
                      </>
                    ) : (
                      <>
                        <MicrophoneIcon className="h-5 w-5 mr-2" />
                        {isClarifying ? 'Answer Question' : 'Start Talking'}
                      </>
                    )}
                  </button>
                </div>

                {transcript && (
                  <div className="bg-gray-50 p-4 rounded-lg mb-4">
                    <h2 className="font-semibold mb-2">Transcript:</h2>
                    <p>{transcript}</p>
                  </div>
                )}

                {isClarifying && context?.clarifying_questions?.length > 0 ? (
                  <div className="bg-blue-50 p-4 rounded-lg mb-4">
                    <h2 className="text-lg font-semibold mb-2">Please answer this question:</h2>
                    <p className="mb-4">{context.clarifying_questions[0]}</p>
                    <p className="text-sm text-gray-600 mb-4">Click the microphone button and speak your answer.</p>
                    <p className="text-sm text-gray-500">Clarification {clarificationCount + 1} of {MAX_CLARIFICATIONS}</p>
                  </div>
                ) : null}

                {recipes.length > 0 && (
                  <div className="mt-8">
                    <h2 className="text-xl font-semibold mb-4">Recommended Recipes:</h2>
                    <div className="grid gap-4">
                      {recipes.map((recipe, index) => (
                        <div key={index} className="bg-white p-4 rounded-lg shadow">
                          <div className="flex justify-between items-start mb-2">
                            <h3 className="font-bold text-lg">{recipe.title}</h3>
                            <span className="text-sm text-gray-500 bg-gray-100 px-2 py-1 rounded">
                              {recipe.source}
                            </span>
                          </div>
                          {recipe.imageUrl && (
                            <img 
                              src={recipe.imageUrl} 
                              alt={recipe.title}
                              className="w-full h-48 object-cover rounded-lg mb-2"
                            />
                          )}
                          {recipe.nutrition ? (
                            <div className="bg-gray-50 p-3 rounded-lg mb-2">
                              <h4 className="font-semibold text-gray-700 mb-1">Nutrition Information:</h4>
                              {recipe.serving_size && (
                                <div className="text-sm text-gray-600 mb-2">
                                  Per {recipe.serving_size.amount} {recipe.serving_size.unit}
                                </div>
                              )}
                              <div className="grid grid-cols-2 gap-2 text-sm">
                                {Object.entries(recipe.nutrition).map(([key, value]) => (
                                  <div key={key} className="flex justify-between">
                                    <span className="text-gray-600 capitalize">{key}:</span>
                                    <span className="font-medium">
                                      {Math.round(value)} {key === 'calories' ? 'kcal' : 'g'}
                                      {recipe.nutrition_confidence && (
                                        <span className="text-xs text-gray-500 ml-1">
                                          ({Math.round(recipe.nutrition_confidence[key] * 100)}% confidence)
                                        </span>
                                      )}
                                    </span>
                                  </div>
                                ))}
                              </div>
                              {recipe.nutrition_notes && recipe.nutrition_notes.length > 0 && (
                                <div className="mt-2 text-xs text-gray-500">
                                  <div className="font-medium mb-1">Notes:</div>
                                  <ul className="list-disc list-inside">
                                    {recipe.nutrition_notes.map((note, index) => (
                                      <li key={index}>{note}</li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                            </div>
                          ) : (
                            <div className="text-sm text-gray-500 italic mb-2">
                              Nutrition information not available for this recipe
                            </div>
                          )}
                          <a 
                            href={recipe.sourceUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-500 hover:text-blue-600"
                          >
                            {recipe.source === 'YouTube' ? 'Watch Recipe' : 'View Recipe'}
                          </a>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {error && (
                  <div className="text-red-500 mt-4">
                    {error}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
