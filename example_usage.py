"""
Example usage of the AP FRQ Grading API.
This script demonstrates how to use the grading service.
"""
import requests
import json

API_BASE_URL = "http://localhost:8000"

def grade_example():
    """Example of grading a single FRQ response."""
    
    # Example AP Biology FRQ
    question_prompt = """
    Explain how the process of natural selection leads to evolution.
    Include in your answer:
    1. The mechanism of natural selection
    2. How variation arises in populations
    3. How selection pressure affects allele frequencies
    """
    
    rubric = """
    Scoring Rubric (10 points total):
    
    Natural Selection Mechanism (4 points):
    - Correctly explains that individuals with advantageous traits survive and reproduce (2 points)
    - Describes how traits are passed to offspring (1 point)
    - Mentions differential survival/reproduction (1 point)
    
    Variation (3 points):
    - Explains that variation comes from mutations and/or sexual reproduction (2 points)
    - Mentions genetic variation in populations (1 point)
    
    Allele Frequency Changes (3 points):
    - Explains that advantageous alleles increase in frequency (2 points)
    - Connects selection to population-level changes (1 point)
    """
    
    student_response = """
    Natural selection is the process where organisms with traits that help them survive
    are more likely to reproduce and pass those traits to their offspring. Over time,
    this leads to changes in the population. Variation comes from mutations and genetic
    recombination during sexual reproduction. When certain traits are advantageous,
    the alleles for those traits become more common in the population, which is evolution.
    """
    
    payload = {
        "student_response": student_response,
        "rubric": rubric,
        "question_prompt": question_prompt,
        "max_points": 10,
        "question_number": "Q1"
    }
    
    print("Sending grading request...")
    response = requests.post(f"{API_BASE_URL}/grade", json=payload)
    
    if response.status_code == 200:
        result = response.json()
        print("\n" + "="*60)
        print("GRADING RESULT")
        print("="*60)
        print(f"Score: {result['score']}/{result['max_points']} ({result['percentage']}%)")
        print(f"\nFeedback:\n{result['feedback']}")
        print(f"\nRubric Alignment:")
        for criterion, score in result['rubric_alignment'].items():
            print(f"  - {criterion}: {score:.2f}")
        print(f"\nTimestamp: {result['timestamp']}")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)


def health_check():
    """Check if the service is healthy."""
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        if response.status_code == 200:
            result = response.json()
            print("Service Status:")
            print(f"  Status: {result['status']}")
            print(f"  Ollama Available: {result['ollama_available']}")
            print(f"  Model: {result['model']}")
            return result['ollama_available']
        else:
            print(f"Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"Error connecting to service: {e}")
        return False


if __name__ == "__main__":
    print("AP FRQ Grading Service - Example Usage\n")
    
    # Check health first
    if not health_check():
        print("\n⚠️  Service is not healthy. Please check:")
        print("  1. Docker containers are running: docker compose ps")
        print("  2. Ollama model is pulled: docker compose exec ollama ollama list")
        print("  3. Service logs: docker compose logs fastapi-app")
        exit(1)
    
    print("\n" + "-"*60)
    grade_example()
