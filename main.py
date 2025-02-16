from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from typing import List
import re
from io import BytesIO
import spacy
from nltk.stem import PorterStemmer
from nltk.tokenize import word_tokenize, sent_tokenize
import pandas as pd
from PyPDF2 import PdfReader
from docx import Document
import nltk
nltk.download('punkt')

app = FastAPI()

# Load spaCy model for NER
nlp = spacy.load("en_core_web_sm")
stemmer = PorterStemmer()

# In-memory storage for extracted criteria
extracted_criteria = []

# Serve HTML UI
@app.get("/", response_class=HTMLResponse)
async def get_ui():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Resume Ranking Tool</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #f4f4f9;
                margin: 0;
                padding: 20px;
                color: #333;
            }
            h1 {
                color: #4CAF50;
            }
            .container {
                max-width: 800px;
                margin: 0 auto;
                background: #fff;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
            }
            .form-group {
                margin-bottom: 15px;
            }
            label {
                display: block;
                margin-bottom: 5px;
                font-weight: bold;
            }
            input[type="file"], textarea {
                width: 100%;
                padding: 10px;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
            button {
                background-color: #4CAF50;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
            }
            button:hover {
                background-color: #45a049;
            }
            .result {
                margin-top: 20px;
                padding: 15px;
                background-color: #e8f5e9;
                border-radius: 4px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Resume Ranking Tool</h1>
            <div class="form-group">
                <label for="jobDescription">Upload Job Description (PDF/DOCX):</label>
                <input type="file" id="jobDescription" accept=".pdf,.docx">
                <button onclick="extractCriteria()">Extract Criteria</button>
            </div>
            <div class="result" id="criteriaResult">
                <!-- Extracted criteria will be displayed here -->
            </div>

            <div class="form-group">
                <label for="resumes">Upload Resumes (PDF/DOCX):</label>
                <input type="file" id="resumes" multiple accept=".pdf,.docx">
                <button onclick="scoreResumes()">Score Resumes</button>
            </div>
            <div class="result" id="scoreResult">
                <!-- Scoring result will be displayed here -->
            </div>
        </div>

        <script>
            // Extract criteria from the uploaded job description
            async function extractCriteria() {
                const fileInput = document.getElementById('jobDescription');
                if (fileInput.files.length === 0) {
                    alert('Please upload a job description file.');
                    return;
                }

                const formData = new FormData();
                formData.append('file', fileInput.files[0]);

                const response = await fetch('/extract-criteria', {
                    method: 'POST',
                    body: formData
                });

                if (response.ok) {
                    const data = await response.json();
                    // Store and display extracted criteria
                    document.getElementById('criteriaResult').innerHTML = `
                        <h3>Extracted Criteria:</h3>
                        <ul>
                            ${data.criteria.map(c => `<li>${c}</li>`).join('')}
                        </ul>
                    `;
                } else {
                    alert('Failed to extract criteria.');
                }
            }

            // Score resumes using the criteria already extracted and displayed
            async function scoreResumes() {
                const fileInput = document.getElementById('resumes');
                if (fileInput.files.length === 0) {
                    alert('Please upload at least one resume.');
                    return;
                }

                // Automatically use criteria stored on the server via the /get-criteria endpoint
                const criteriaResponse = await fetch('/get-criteria');
                if (!criteriaResponse.ok) {
                    alert('No criteria found. Please extract criteria first.');
                    return;
                }
                const criteriaData = await criteriaResponse.json();
                const criteria = criteriaData.criteria;

                const formData = new FormData();
                // Append criteria from the stored extracted criteria (no manual input)
                criteria.forEach(c => formData.append('criteria', c));
                for (const file of fileInput.files) {
                    formData.append('files', file);
                }

                const response = await fetch('/score-resumes', {
                    method: 'POST',
                    body: formData
                });

                if (response.ok) {
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'scores.xlsx';
                    a.click();
                    document.getElementById('scoreResult').innerHTML = `
                        <h3>Resumes scored successfully!</h3>
                        <p>Download the <a href="${url}" download>Excel file</a>.</p>
                    `;
                } else {
                    alert('Failed to score resumes.');
                }
            }
        </script>
    </body>
    </html>
    """

# Extract criteria from job description
@app.post("/extract-criteria")
async def extract_criteria_endpoint(file: UploadFile = File(...)):
    if not file.filename.endswith(('.pdf', '.docx')):
        raise HTTPException(400, "Unsupported file type. Only PDF and DOCX are allowed.")
    
    content = await file.read()
    text = ""
    if file.filename.endswith('.pdf'):
        text = extract_text_from_pdf(BytesIO(content))
    elif file.filename.endswith('.docx'):
        text = extract_text_from_docx(BytesIO(content))
    
    global extracted_criteria
    extracted_criteria = extract_criteria(text)
    return {"criteria": extracted_criteria}

# Get extracted criteria
@app.get("/get-criteria")
async def get_criteria():
    if not extracted_criteria:
        raise HTTPException(404, "No criteria found. Please extract criteria first.")
    return {"criteria": extracted_criteria}

# Score resumes against criteria and return an Excel file with scores
@app.post("/score-resumes")
async def score_resumes_endpoint(
    criteria: List[str] = Form(...),
    files: List[UploadFile] = File(...)
):
    results = []
    for file in files:
        if not file.filename.endswith(('.pdf', '.docx')):
            continue
        
        content = await file.read()
        text = ""
        if file.filename.endswith('.pdf'):
            text = extract_text_from_pdf(BytesIO(content))
        elif file.filename.endswith('.docx'):
            text = extract_text_from_docx(BytesIO(content))
        
        name = extract_name(text)
        resume_sentences = sent_tokenize(text)
        scores = []
        for criterion in criteria:
            criterion_set = preprocess(criterion)
            max_sim = 0
            for sentence in resume_sentences:
                sentence_set = preprocess(sentence)
                sim = jaccard_similarity(criterion_set, sentence_set)
                if sim > max_sim:
                    max_sim = sim
            score = round(max_sim * 5)
            scores.append(score)
        total = sum(scores)
        results.append({"name": name, "scores": scores, "total": total})
    
    column_names = [get_column_name(criterion) for criterion in criteria]
    df_data = []
    for res in results:
        row = {"Candidate Name": res["name"]}
        for i, score in enumerate(res["scores"]):
            row[column_names[i]] = score
        row["Total Score"] = res["total"]
        df_data.append(row)
    
    df = pd.DataFrame(df_data)
    excel_file = BytesIO()
    df.to_excel(excel_file, index=False)
    excel_file.seek(0)
    
    return StreamingResponse(
        excel_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=scores.xlsx"}
    )

# Helper functions
def extract_text_from_pdf(file):
    pdf_reader = PdfReader(file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

def extract_text_from_docx(file):
    doc = Document(file)
    text = "\n".join([para.text for para in doc.paragraphs])
    return text

def extract_criteria(text):
    trigger_phrases = [
        'must have', 'required', 'qualifications', 'experience',
        'skills', 'certification', 'proficient', 'knowledge of',
        'ability to', 'degree in', 'years of'
    ]
    sentences = sent_tokenize(text)
    criteria = []
    for sentence in sentences:
        sentence_lower = sentence.lower()
        if any(trigger in sentence_lower for trigger in trigger_phrases):
            criteria.append(sentence.strip())
    return criteria

def preprocess(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    tokens = word_tokenize(text)
    stemmed_tokens = [stemmer.stem(token) for token in tokens]
    return set(stemmed_tokens)

def jaccard_similarity(set1, set2):
    intersection = set1.intersection(set2)
    union = set1.union(set2)
    return len(intersection) / len(union) if union else 0

def extract_name(text):
    doc = nlp(text)
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            return ent.text
    lines = text.split('\n')
    for line in lines:
        stripped = line.strip()
        if stripped:
            return stripped
    return "Unknown"

def get_column_name(criterion):
    doc = nlp(criterion)
    noun_chunks = list(doc.noun_chunks)
    if noun_chunks:
        last_noun = noun_chunks[-1].text
        return last_noun.title()
    return criterion

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
