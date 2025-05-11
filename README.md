# Recipe Voice Assistant

AI voice assistant for recipe discovery and nutrition information.

## Features

- Voice-based interaction for recipe search
- Natural conversation with clarifying questions
- Detailed recipe information including:
  - Nutrition facts
  - Serving sizes
  - Recipe sources
  - Images
- Real-time voice feedback
- Multi-source recipe search

## Tech Stack

- Frontend: React, TypeScript, Tailwind CSS
- Backend: Python, Flask
- AI: Google Gemini
- Speech: Web Speech API

## Setup

### Backend

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create and activate virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   export GOOGLE_API_KEY=your_api_key
   ```

5. Run the server:
   ```bash
   python app.py
   ```

### Frontend

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm run dev
   ```

## Usage

1. Open the application in your browser
2. Click the microphone button to start speaking
3. Ask for recipes (e.g., "Find me some healthy dinner recipes")
4. Answer any clarifying questions
5. Browse through the suggested recipes

## License

MIT 