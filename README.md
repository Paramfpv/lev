# Longevity RAG Chatbot

A RAG (Retrieval-Augmented Generation) chatbot for querying longevity and human optimization protocols, with both CLI and Streamlit interface.

## Features

- 📚 Query 100+ longevity protocols on supplements, exercise, sleep, and more
- 🤖 AI-powered responses using Groq's Llama 3.1 model
- 💬 Interactive chat interface with Streamlit
- 🔍 Protocol search and filtering
- 📊 Full documentation and metadata

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file in the project root:

```
GROQ_API_KEY=your_groq_api_key_here
```

Get your API key from: https://console.groq.com/

### 3. Process the Data (First Time Only)

```bash
python data_ingestion_pipeline.py
```

This will load all protocols from `protocols_data/` and save processed chunks to `processed_data/`.

## Usage

### Streamlit App (Recommended)

```bash
streamlit run app.py
```

The app will open in your browser with a user-friendly interface featuring:
- Chat interface for asking questions
- Sidebar with searchable protocol list
- Quick action buttons for common queries
- Interactive protocol buttons

### Command Line Interface

```bash
python retrieval_pipeline.py
```

## Example Queries


## Project Structure
 
core/ - Data ingestion and retrieval logic
backend/ - API and Supabase integration
frontend/ - Temporary/testing files
processed_data/ - Output data
protocols_data/ - Input documents


```
.
├── app.py                         # Streamlit web app
├── data_ingestion_pipeline.py     # Data processing pipeline
├── retrieval_pipeline.py          # RAG chatbot backend
├── processed_data/                # Processed chunks and metadata
│   ├── all_chunks.json
│   └── metadata.json
├── protocols_data/                # Source protocol files
├── requirements.txt               # Python dependencies
└── README.md                      # This file
```

## Backend Architecture

The backend consists of two main components:

1. **Data Ingestion Pipeline** (`data_ingestion_pipeline.py`):
   - Loads protocol files from `protocols_data/`
   - Chunks documents into smaller pieces
   - Saves processed chunks to JSON

2. **Retrieval Pipeline** (`retrieval_pipeline.py`):
   - Loads processed chunks
   - Implements semantic search
   - Generates responses using Groq API
   - Handles special commands and protocol queries

The Streamlit app (`app.py`) provides a user-friendly interface without modifying the backend logic.

## License

MIT License
