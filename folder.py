import requests
import json

# Azure OpenAI API credentials
API_KEY = "aa4f2f35c7634fcb8f5b652bbfb36926"
DEPLOYMENT_NAME = "gpt-4o"
API_URL = "https://nw-tech-dev.openai.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2023-03-15-preview"

def generate_code_from_description(description):
    """
    Generate Python code using Azure OpenAI GPT-4o.
    """
    headers = {
        "Content-Type": "application/json",
        "api-key": API_KEY
    }

    # Modified prompt to request code generation based on folder.py
    payload = {
        "messages": [{
            "role": "user", 
            "content": f"Generate a Python script based on this description: {description}. Return only the code without any explanations or markdown."
        }],
        "temperature": 0.7,
        "max_tokens": 800
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status()
        generated_code = response.json()["choices"][0]["message"]["content"]
        
        # Clean up the generated code
        generated_code = generated_code.strip()
        if generated_code.startswith("```python"):
            generated_code = generated_code.split("```")[1].strip()
        if generated_code.startswith("python"):
            generated_code = generated_code[6:].strip()
            
        return generated_code
    except requests.exceptions.RequestException as e:
        return f"Error: {str(e)}\nResponse: {response.text if 'response' in locals() else 'No response'}"

if __name__ == "__main__":
    # Read the content of folder.py
    with open(__file__, 'r') as file:
        folder_content = file.read()
    
    user_description = input("Enter code description: ")
    generated_code = generate_code_from_description(user_description)
    
    if not generated_code.startswith("Error:"):
        # Write the generated code to generated.py
        with open('generated.py', 'w') as file:
            file.write(generated_code)
        print("\nCode has been generated and saved to 'generated.py'")
        print("\nGenerated Code:")
        print(generated_code)
    else:
        print("\nError occurred:")
        print(generated_code)
