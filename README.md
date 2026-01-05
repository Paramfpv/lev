# LEV Longevity RAG Chatbot

An AI-powered RAG (Retrieval-Augmented Generation) API for querying longevity and human optimization protocols.

## Features

- 📚 **RAG Pipeline**: Semantic search over 100+ longevity protocols
- 🚀 **FastAPI Backend**: Robust API for chat, history, and authentication
- 🧠 **AI Models**: Uses Groq (Llama 3.1) for fast inference
- 🗄️ **Database**: Supabase for user storage and chat history
- 🔍 **Vector DB**: ChromaDB Cloud for storing and retrieving protocol chunks

## Project Structure

```
Lev/
├── core/                        # Core Application Logic
│   ├── data_ingestion.py        # Pipeline to process & chunk .txt files
│   ├── retrieval_pipeline.py    # RAG chatbot logic & Groq integration
│   └── supabase_utils.py        # Database connection utilities
├── protocols_data/              # Source text files (Knowledge Base)
├── processed_data/              # JSON output of processed chunks
├── main.py                      # FastAPI Entry Point
├── schema.sql                   # Database Structure
├── requirements.txt             # Project Dependencies
└── Dockerfile                   # Deployment Configuration
```

## Setup & Local Development

1. **Clone the repository**
   ```bash
   git clone <repo-url>
   cd Lev
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**
   Duplicate `.env.example` to `.env` and fill in your keys:
   ```bash
   cp .env.example .env
   ```
   **Required Keys:**
   - `GROQ_API_KEY`: For AI generation
   - `SUPABASE_URL` & `SUPABASE_KEY`: For database
   - `CHROMA_API_KEY`, `CHROMA_TENANT_ID`, `CHROMA_DATABASE`: For vector search

4. **Initialize Database**
   - Run the SQL commands in `schema.sql` in your Supabase SQL Editor.

5. **Run the API**
   ```bash
   uvicorn main:app --reload
   ```
   API will be available at `http://localhost:8000`.

## API Documentation

Once running, access the automatic documentation:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### Key Endpoints
- `POST /chat`: Send a message to the bot
- `GET /history/{user_id}`: Get past conversations
- `GET /health`: Check API and database status

## Deployment

This project includes a `Dockerfile` and is ready for deployment on platforms like **Railway**, **Render**, or **DigitalOcean App Platform**.

**Environment Variables for Deployment:**
Ensure all variables from `.env.example` are set in your deployment environment settings.
