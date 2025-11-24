"""
Main RAG System Connector
Connects the data ingestion pipeline with the retrieval pipeline
"""

from data_ingestion_pipeline import run_simple_pipeline
from retrieval_pipeline import LongevityRAGChatbot

def setup_rag_system():
    """
    Set up the complete RAG system
    """
    print("Setting up Longevity RAG System...")
    
    # Check if processed data exists
    import os
    if not os.path.exists("processed_data/all_chunks.json"):
        print("Processed data not found. Running data ingestion pipeline...")
        run_simple_pipeline()
    else:
        print("Processed data found. Skipping ingestion.")
    
    # Initialize chatbot
    chatbot = LongevityRAGChatbot()
    return chatbot

def main():
    """
    Main function to run the complete RAG system
    """
    chatbot = setup_rag_system()
    
    print("\n" + "=" * 60)
    print("🤖 LONGEVITY RAG CHATBOT READY!")
    print("=" * 60)
    print("Ask me about longevity protocols, supplements, exercise, sleep, nutrition, and more!")
    print("\nCommands:")
    print("- 'list protocols' - Show all available protocols")
    print("- 'list protocols sleep' - Show protocols related to sleep")
    print("- 'protocol Magnesium' - Get detailed info about Magnesium")
    print("- Or just ask any question!")
    print("\nType 'quit' or 'exit' to end the session.")
    print("=" * 60)
    
    while True:
        try:
            # Get user input
            user_input = input("\n💬 You: ").strip()
            
            # Check for exit commands
            if user_input.lower() in ['quit', 'exit', 'bye', 'goodbye']:
                print("\n👋 Thanks for using the Longevity RAG Chatbot! Stay healthy!")
                break
            
            # Skip empty inputs
            if not user_input:
                continue
            
            # Get response from chatbot
            print("\n🤖 Bot:")
            response = chatbot.chat(user_input)
            print(response)
            
        except KeyboardInterrupt:
            print("\n\n👋 Thanks for using the Longevity RAG Chatbot! Stay healthy!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("Please try again or type 'quit' to exit.")

if __name__ == "__main__":
    main()