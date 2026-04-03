import sys
sys.path.insert(0, ".")
from llm.rag import seed_fraud_cases

if __name__ == "__main__":
    seed_fraud_cases()
    print("Knowledge base seeding complete.")
