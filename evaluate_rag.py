#!/usr/bin/env python3
"""
RAG System Evaluation using RAGAS

This script evaluates the RAG system using the RAGAS framework which provides
metrics like context precision, context recall, faithfulness, and answer relevancy.

Usage:
    python evaluate_rag.py --endpoint http://localhost:8000 --test-set evaluation_dataset.json

    Or with deployed system:
    python evaluate_rag.py --endpoint https://your-alb-url.amazonaws.com
"""

import argparse
import json
import os
import sys
from typing import List, Dict, Any
import requests
from datetime import datetime

try:
    from ragas import evaluate
    from ragas.metrics import (
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
        answer_similarity,
        answer_correctness,
    )
    from datasets import Dataset
except ImportError:
    print("ERROR: Required packages not installed.")
    print("Please install: pip install ragas datasets langchain-openai")
    sys.exit(1)


class RAGEvaluator:
    """Evaluates RAG system using RAGAS framework"""

    def __init__(self, endpoint_url: str, openai_api_key: str = None):
        """
        Initialize the evaluator

        Args:
            endpoint_url: The RAG system endpoint (e.g., http://localhost:8000 or ALB URL)
            openai_api_key: OpenAI API key for RAGAS metrics (uses env var if not provided)
        """
        self.endpoint_url = endpoint_url.rstrip('/')
        self.openai_api_key = openai_api_key or os.getenv('OPENAI_API_KEY')

        if not self.openai_api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY env var or pass as argument")

        # Set for RAGAS
        os.environ['OPENAI_API_KEY'] = self.openai_api_key

    def query_rag_system(self, question: str, conversation_id: str = None) -> Dict[str, Any]:
        """
        Query the RAG system and get response with context

        Args:
            question: The question to ask
            conversation_id: Optional conversation ID for context

        Returns:
            Dictionary with answer and contexts
        """
        try:
            payload = {
                "message": question,
                "provider": "openai",
                "model": "gpt-4o-mini"
            }

            if conversation_id:
                payload["conversation_id"] = conversation_id

            response = requests.post(
                f"{self.endpoint_url}/chat",
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            data = response.json()

            return {
                "answer": data.get("response", ""),
                "contexts": data.get("sources", []),
                "conversation_id": data.get("conversation_id")
            }

        except requests.exceptions.RequestException as e:
            print(f"Error querying RAG system: {e}")
            return {"answer": "", "contexts": []}

    def load_test_dataset(self, filepath: str) -> List[Dict[str, Any]]:
        """
        Load test dataset from JSON file

        Expected format:
        [
            {
                "question": "What is...",
                "ground_truth": "The answer is...",
                "reference_contexts": ["context1", "context2"]  # Optional
            },
            ...
        ]

        Args:
            filepath: Path to JSON file with test cases

        Returns:
            List of test cases
        """
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Test dataset not found: {filepath}")
            print("Creating sample dataset...")
            return self.create_sample_dataset()

    def create_sample_dataset(self) -> List[Dict[str, Any]]:
        """
        Create a sample test dataset for demonstration

        Returns:
            Sample test cases
        """
        sample_dataset = [
            {
                "question": "What are the main features of the system?",
                "ground_truth": "The system has multiple features including document management, conversation history, and RAG capabilities.",
            },
            {
                "question": "How does the vector search work?",
                "ground_truth": "Vector search uses embeddings to find semantically similar documents in the knowledge base.",
            },
            {
                "question": "What models are supported?",
                "ground_truth": "The system supports OpenAI models like GPT-4 and GPT-3.5-turbo, as well as local models via Ollama.",
            }
        ]

        # Save sample dataset
        with open('sample_evaluation_dataset.json', 'w') as f:
            json.dump(sample_dataset, f, indent=2)

        print("Created sample dataset: sample_evaluation_dataset.json")
        print("Please replace with your actual test questions and ground truth answers.\n")

        return sample_dataset

    def prepare_ragas_dataset(self, test_cases: List[Dict[str, Any]]) -> Dataset:
        """
        Query RAG system for each test case and prepare RAGAS dataset

        Args:
            test_cases: List of test cases with questions and ground truth

        Returns:
            RAGAS Dataset ready for evaluation
        """
        print(f"Querying RAG system for {len(test_cases)} test cases...\n")

        ragas_data = {
            "question": [],
            "answer": [],
            "contexts": [],
            "ground_truth": []
        }

        for i, test_case in enumerate(test_cases, 1):
            question = test_case["question"]
            ground_truth = test_case["ground_truth"]

            print(f"[{i}/{len(test_cases)}] Processing: {question[:60]}...")

            # Query RAG system
            result = self.query_rag_system(question)

            ragas_data["question"].append(question)
            ragas_data["answer"].append(result["answer"])
            ragas_data["contexts"].append(result["contexts"])
            ragas_data["ground_truth"].append(ground_truth)

        print("\nDataset preparation complete.\n")

        return Dataset.from_dict(ragas_data)

    def run_evaluation(
        self,
        dataset: Dataset,
        metrics: List = None
    ) -> Dict[str, Any]:
        """
        Run RAGAS evaluation on the dataset

        Args:
            dataset: RAGAS Dataset with questions, answers, contexts, ground_truth
            metrics: List of RAGAS metrics to evaluate (uses default if None)

        Returns:
            Evaluation results
        """
        if metrics is None:
            metrics = [
                faithfulness,           # Measures factual accuracy
                answer_relevancy,       # Measures how relevant answer is to question
                context_precision,      # Measures if relevant contexts are ranked higher
                context_recall,         # Measures if all relevant info is retrieved
                answer_correctness,     # Measures correctness compared to ground truth
            ]

        print("Running RAGAS evaluation...")
        print(f"Metrics: {[m.name for m in metrics]}\n")

        result = evaluate(
            dataset=dataset,
            metrics=metrics,
        )

        return result

    def print_results(self, results: Dict[str, Any]):
        """
        Print evaluation results in a readable format

        Args:
            results: RAGAS evaluation results
        """
        print("\n" + "="*70)
        print("RAG SYSTEM EVALUATION RESULTS")
        print("="*70)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Endpoint: {self.endpoint_url}")
        print("-"*70)

        # Overall scores
        for metric, score in results.items():
            if metric != 'per_question':
                print(f"{metric:.<50} {score:.4f}")

        print("="*70)

        # Interpretation guide
        print("\nInterpretation Guide:")
        print("  Faithfulness (0-1):       Higher = More factually accurate")
        print("  Answer Relevancy (0-1):   Higher = More relevant to question")
        print("  Context Precision (0-1):  Higher = Better context ranking")
        print("  Context Recall (0-1):     Higher = More complete retrieval")
        print("  Answer Correctness (0-1): Higher = Closer to ground truth")
        print("\nNote: Scores above 0.7 are generally considered good.")

    def save_results(self, results: Dict[str, Any], output_file: str = None):
        """
        Save evaluation results to JSON file

        Args:
            results: RAGAS evaluation results
            output_file: Output filepath (auto-generated if None)
        """
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"rag_evaluation_results_{timestamp}.json"

        results_dict = {
            "timestamp": datetime.now().isoformat(),
            "endpoint": self.endpoint_url,
            "metrics": {k: float(v) for k, v in results.items() if k != 'per_question'}
        }

        with open(output_file, 'w') as f:
            json.dump(results_dict, f, indent=2)

        print(f"\nResults saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate RAG system using RAGAS framework"
    )
    parser.add_argument(
        '--endpoint',
        default='http://localhost:8000',
        help='RAG system endpoint URL (default: http://localhost:8000)'
    )
    parser.add_argument(
        '--test-set',
        help='Path to test dataset JSON file'
    )
    parser.add_argument(
        '--openai-api-key',
        help='OpenAI API key (or set OPENAI_API_KEY env var)'
    )
    parser.add_argument(
        '--output',
        help='Output file for results (default: auto-generated)'
    )

    args = parser.parse_args()

    try:
        # Initialize evaluator
        print("Initializing RAG Evaluator...\n")
        evaluator = RAGEvaluator(
            endpoint_url=args.endpoint,
            openai_api_key=args.openai_api_key
        )

        # Load or create test dataset
        if args.test_set:
            test_cases = evaluator.load_test_dataset(args.test_set)
        else:
            print("No test set provided. Using sample dataset.\n")
            test_cases = evaluator.create_sample_dataset()

        # Prepare dataset by querying RAG system
        dataset = evaluator.prepare_ragas_dataset(test_cases)

        # Run evaluation
        results = evaluator.run_evaluation(dataset)

        # Display and save results
        evaluator.print_results(results)
        evaluator.save_results(results, args.output)

    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
