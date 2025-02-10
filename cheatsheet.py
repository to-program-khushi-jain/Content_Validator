import streamlit as st
import os
import zipfile
import json
import requests
from supabase import create_client
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OpenAIEmbeddings
import tempfile

# Azure OpenAI API credentials
API_KEY = "aa4f2f35c7634fcb8f5b652bbfb36926"
DEPLOYMENT_NAME = "gpt-4o"
API_URL = "https://nw-tech-dev.openai.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2023-03-15-preview"

# Supabase credentials
SUPABASE_URL = "https://qkvkyxwhfnxaaamaiywp.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFrdmt5eHdoZm54YWFhbWFpeXdwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzkwOTc0ODksImV4cCI6MjA1NDY3MzQ4OX0.WsUMNRC0A-qD1Ef3BRKgJFBMT9AqJW-gFnUjsgMt53Y"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def delete_cheatsheet(sheet_id):
    """Delete a cheatsheet from Supabase"""
    try:
        response = supabase.table('cheatsheets').delete().eq('id', sheet_id).execute()
        return True
    except Exception as e:
        st.error(f"Error deleting from database: {str(e)}")
        return False

def init_vector_store():
    """Initialize the vector store"""
    return Chroma(
        collection_name="cheatsheets",
        embedding_function=OpenAIEmbeddings()
    )

def save_cheatsheet(content, filename):
    """Save cheatsheet to Supabase"""
    try:
        data = {
            'filename': filename,
            'content': content
        }
        supabase.table('cheatsheets').insert(data).execute()
        return True
    except Exception as e:
        st.error(f"Error saving to database: {str(e)}")
        return False

def get_stored_cheatsheets():
    """Retrieve all stored cheatsheets"""
    try:
        response = supabase.table('cheatsheets').select("*").execute()
        return response.data
    except Exception as e:
        st.error(f"Error retrieving from database: {str(e)}")
        return []

def extract_question_content(question_data):
    """Extract all relevant content from a question for verification"""
    content = []
    
    # Extract question ID
    question_id = question_data.get('question_id', '')
    
    # Extract question text
    if 'question_text' in question_data:
        content.append(("Question Text", question_data['question_text']))
    elif 'question' in question_data and isinstance(question_data['question'], dict):
        content.append(("Question Text", question_data['question'].get('content', '')))
    
    # Extract options for multiple choice questions
    if 'options' in question_data:
        options_text = []
        for option in question_data['options']:
            if isinstance(option, dict):
                options_text.append(option.get('content', ''))
        if options_text:
            content.append(("Options", "\n".join(options_text)))
    
    # Extract code blocks from different question types
    if 'solution' in question_data:
        for lang_section in question_data['solution']:
            code_blocks = []
            for block in lang_section.get('code_blocks', []):
                code_blocks.append(block.get('code', ''))
            if code_blocks:
                content.append((f"Code ({lang_section['language']})", "\n".join(code_blocks)))
    
    # Extract code from code_metadata
    if 'code_metadata' in question_data:
        for code_meta in question_data['code_metadata']:
            if 'code_data' in code_meta:
                content.append((f"Code ({code_meta['language']})", code_meta['code_data']))
    
    # Extract explanation
    if 'explanation_for_answer' in question_data:
        explanation = question_data['explanation_for_answer'].get('content', '')
        if explanation:
            content.append(("Explanation", explanation))
    
    return question_id, content

def verify_content_with_gpt(content_to_verify, cheatsheet_content):
    """Optimized verification function"""
    headers = {
        "Content-Type": "application/json",
        "api-key": API_KEY
    }

    # Optimize prompt for faster processing
    prompt = f"""
    Quick analysis: Is this content covered by the cheatsheet? Only check main concepts.
    
    Content: {content_to_verify[:1000]}  # Limit content length
    
    Cheatsheet: {cheatsheet_content[:2000]}  # Limit cheatsheet length
    
    Answer YES or NO with one brief reason.
    """

    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 150  # Reduced from 1000
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error in verification: {str(e)}"

def process_questions_file(file_path, cheatsheet_content):
    """Optimized file processing"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            questions = json.load(f)
        
        if not isinstance(questions, list):
            questions = [questions]
        
        # Process questions in batches
        batch_size = 5
        results = []
        
        for i in range(0, len(questions), batch_size):
            batch = questions[i:i + batch_size]
            batch_results = []
            
            for question in batch:
                question_id, content_parts = extract_question_content(question)
                full_content = "\n".join([f"{title}:\n{text}" for title, text in content_parts])
                
                verification_result = verify_content_with_gpt(full_content, cheatsheet_content)
                batch_results.append({
                    'question_id': question_id,
                    'verification_result': verification_result,
                    'content_analyzed': content_parts
                })
            
            results.extend(batch_results)
            # Show progress
            st.progress((i + len(batch)) / len(questions))
            
        return results
    
    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
        return []

def main():
    st.title("Enhanced Question Content Verification System")
    
    with st.sidebar:
        st.header("Upload Cheatsheets")
        uploaded_file = st.file_uploader("Choose a markdown file", type=['md'])
        
        if uploaded_file:
            content = uploaded_file.read().decode()
            if save_cheatsheet(content, uploaded_file.name):
                st.success(f"Successfully uploaded {uploaded_file.name}")
        
        st.header("Stored Cheatsheets")
        stored_sheets = get_stored_cheatsheets()
        
        # Display and delete functionality for stored cheatsheets
        for sheet in stored_sheets:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(sheet['filename'])
            with col2:
                if st.button("Delete", key=f"delete_{sheet['id']}"):
                    try:
                        supabase.table('cheatsheets').delete().eq('id', sheet['id']).execute()
                        st.success(f"Deleted {sheet['filename']}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error deleting: {str(e)}")
    
    # Main content area
    stored_sheets = get_stored_cheatsheets()
    if not stored_sheets:
        st.warning("Please upload some cheatsheets first!")
        return
        
    all_content = "\n".join([sheet['content'] for sheet in stored_sheets])
    
    st.header("Question Verification")
    zip_file = st.file_uploader("Upload ZIP file containing questions", type=['zip'])
    
    if zip_file:
        with st.spinner("Analyzing questions..."):
            with tempfile.TemporaryDirectory() as tmp_dir:
                with zipfile.ZipFile(zip_file) as z:
                    z.extractall(tmp_dir)
                
                questions_with_issues = []
                folders_processed = set()
                
                # Process all JSON files in all folders
                for root, dirs, files in os.walk(tmp_dir):
                    for file in files:
                        if file.endswith('.json'):
                            folder_name = os.path.basename(os.path.dirname(os.path.join(root, file)))
                            if folder_name == '':
                                folder_name = os.path.splitext(file)[0]
                            
                            folders_processed.add(folder_name)
                            
                            # Process and verify questions
                            file_path = os.path.join(root, file)
                            results = process_questions_file(file_path, all_content)
                            
                            # Check for issues
                            for result in results:
                                if 'NO' in result['verification_result'].upper():
                                    questions_with_issues.append({
                                        'folder': folder_name,
                                        'question_id': result['question_id'],
                                        'details': result['verification_result']
                                    })
                
                # Display results
                st.subheader("Analysis Results")
                st.write(f"Processed {len(folders_processed)} folders")
                
                if questions_with_issues:
                    st.error(f"Found {len(questions_with_issues)} questions with content not covered in cheatsheets")
                    for issue in questions_with_issues:
                        with st.expander(f"Question ID: {issue['question_id']} (Folder: {issue['folder']})"):
                            st.write(issue['details'])
                else:
                    st.success("All question content is covered by the cheatsheets")

if __name__ == "__main__":
    main()