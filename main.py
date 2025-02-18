import os
import re
import json
import logging
from typing import List, Dict
from fastapi import FastAPI, File, UploadFile, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from io import BytesIO
from openai import OpenAI
from openai.types.chat import ChatCompletion
from pypdf import PdfReader
from docx import Document
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Smart Resume Analyzer API",
    description="API for automated resume ranking against job descriptions",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

# Constants
MAX_FILES = 20
MAX_CRITERIA = 15
ALLOWED_MIME_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx"
}

class APIError(Exception):
    """Custom exception for API errors"""
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code

def validate_inputs(files: List[UploadFile], criteria: List[str] = None):
    """Validate input files and criteria"""
    if len(files) > MAX_FILES:
        raise APIError(f"Maximum {MAX_FILES} files allowed", status.HTTP_400_BAD_REQUEST)
    
    if criteria and len(criteria) > MAX_CRITERIA:
        raise APIError(f"Maximum {MAX_CRITERIA} criteria allowed", status.HTTP_400_BAD_REQUEST)
    
    for file in files:
        if file.content_type not in ALLOWED_MIME_TYPES:
            raise APIError(
                f"Unsupported file type: {file.content_type}. Allowed: PDF, DOCX",
                status.HTTP_400_BAD_REQUEST
            )

def extract_text(file: UploadFile) -> str:
    """Robust text extraction from PDF/DOCX files"""
    try:
        content = file.file.read()
        if file.content_type == "application/pdf":
            reader = PdfReader(BytesIO(content))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        elif "wordprocessingml.document" in file.content_type:
            doc = Document(BytesIO(content))
            return "\n".join(para.text for para in doc.paragraphs if para.text.strip())
        return ""
    except Exception as e:
        logger.error(f"Text extraction failed: {str(e)}")
        raise APIError("File processing error", status.HTTP_400_BAD_REQUEST)

async def get_llm_response(prompt: str, system_msg: str, json_mode: bool = False) -> str:
    """Robust LLM communication with retries and validation"""
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": prompt}
    ]
    
    for attempt in range(3):
        try:
            response: ChatCompletion = client.chat.completions.create(
                model="gpt-3.5-turbo-0125",
                messages=messages,
                temperature=0.1,
                response_format={"type": "json_object"} if json_mode else None,
                timeout=15
            )
            content = response.choices[0].message.content.strip()
            
            if not content:
                raise ValueError("Empty response from LLM")
                
            return content
        except Exception as e:
            if attempt == 2:
                logger.error(f"LLM API failed: {str(e)}")
                raise APIError("LLM service unavailable", status.HTTP_503_SERVICE_UNAVAILABLE)
            time.sleep(0.5 * (attempt + 1))

def parse_criteria_response(response: str) -> List[str]:
    """Advanced criteria parsing with multiple fallback strategies"""
    try:
        # Clean JSON response
        response = re.sub(r'(?i)^\s*(json|response|criteria)\s*[:\-]?\s*', '', response)
        response = response.strip('` \n\t\r')
        
        # Parse JSON
        data = json.loads(response)
        
        # Handle various JSON structures
        if isinstance(data, list):
            return [str(item) for item in data if item]
            
        if isinstance(data, dict):
            for key in ['criteria', 'requirements', 'key_skills', 'qualifications']:
                if key in data and isinstance(data[key], list):
                    return [str(item) for item in data[key] if item]
            
            # Find first suitable list
            for value in data.values():
                if isinstance(value, list) and all(isinstance(i, str) for i in value):
                    return value
        
        raise ValueError("Unsupported JSON structure")
    except json.JSONDecodeError:
        # Fallback to line parsing
        lines = [line.strip(' -*•') for line in response.split('\n') if line.strip()]
        return lines[:MAX_CRITERIA]

def sanitize_column_name(name: str) -> str:
    """Create safe column names for CSV"""
    return re.sub(r'[^a-zA-Z0-9_]', '_', name)[:50]

def validate_score(score: int) -> int:
    """Ensure scores are within 0-5 range"""
    return max(0, min(5, score))

async def extract_candidate_name(text: str) -> str:
    """Accurate name extraction from resume text"""
    prompt = f"""Extract the candidate's full name from this resume. 
    Return ONLY the name in format 'FirstName LastName'. 
    If not found, return 'Unknown Candidate'.\n\n{text[:3000]}"""
    
    response = await get_llm_response(
        prompt=prompt,
        system_msg="You are an expert resume parser. Extract resume information accurately."
    )
    
    # Validate name format
    if re.match(r'^[A-Z][a-z]+(\s[A-Z][a-z]+)+$', response):
        return response
    return "Unknown Candidate"

@app.post("/extract-criteria",
         summary="Extract key criteria from job description",
         responses={
             200: {
                 "description": "Successfully extracted criteria",
                 "content": {
                     "application/json": {
                         "example": {
                             "criteria": ["Python", "5 years experience", "Bachelor's degree"]
                         }
                     }
                 }
             },
             400: {"description": "Invalid input"},
             500: {"description": "Processing error"}
         })
async def extract_criteria(file: UploadFile = File(...)):
    """
    Extract key ranking criteria from a job description document (PDF/DOCX).
    Returns structured JSON with technical requirements and qualifications.
    """
    try:
        validate_inputs([file])
        text = extract_text(file)
        
        system_msg = """You are a senior HR analyst. Extract measurable, objective criteria:
        - Technical skills with proficiency levels
        - Required certifications
        - Experience requirements (years/technologies)
        - Education qualifications
        Exclude soft skills and company-specific information."""
        
        prompt = f"""Analyze this job description and extract key ranking criteria.
        Return JSON format: {{"criteria": ["item1", "item2"]}}
        Job Description:\n{text[:10000]}"""
        
        raw_response = await get_llm_response(prompt, system_msg, json_mode=True)
        criteria = parse_criteria_response(raw_response)
        
        if not criteria:
            raise APIError("No criteria extracted", status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        return JSONResponse({"criteria": criteria[:MAX_CRITERIA]})
    
    except APIError as e:
        raise HTTPException(e.status_code, detail=str(e))
    except Exception as e:
        logger.error(f"Criteria extraction failed: {str(e)}")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Processing failed")

@app.post("/score-resumes",
         summary="Score resumes against criteria",
         responses={
             200: {
                 "content": {
                     "text/csv": {
                         "example": "Candidate Name,Python,5 years experience,Bachelor's degree,Total Score\nJohn Doe,5,4,3,12\n"
                     }
                 },
                 "description": "CSV scores"
             },
             400: {"description": "Invalid input"},
             500: {"description": "Processing error"}
         })
async def score_resumes(
    criteria: List[str] = [],
    files: List[UploadFile] = File(...)
):
    """
    Score multiple resumes against provided criteria.
    Returns CSV with scores (0-5) for each criterion and total score.
    """
    try:
        validate_inputs(files, criteria)
        if not criteria:
            raise APIError("No criteria provided", status.HTTP_400_BAD_REQUEST)
            
        results = []
        for file in files:
            try:
                text = extract_text(file)
                candidate_name = await extract_candidate_name(text)
                
                scores = {"Candidate Name": candidate_name}
                total = 0
                
                for criterion in criteria:
                    prompt = f"""Evaluate this resume against: '{criterion}'
                    Score 0-5 based on explicit mentions and relevance.
                    Return ONLY the integer score.\n\nResume Excerpt:\n{text[:5000]}"""
                    
                    response = await get_llm_response(
                        prompt=prompt,
                        system_msg="You are a technical recruiter. Score resumes objectively."
                    )
                    
                    score = validate_score(int(response.strip()))
                    scores[criterion] = score
                    total += score
                
                scores["Total Score"] = total
                results.append(scores)
            
            except Exception as e:
                logger.warning(f"Skipped {file.filename}: {str(e)}")
                continue
                
        if not results:
            raise APIError("No valid resumes processed", status.HTTP_400_BAD_REQUEST)
        
        # Create CSV with sanitized headers
        df = pd.DataFrame(results)
        sanitized_columns = {col: sanitize_column_name(col) for col in df.columns}
        df.rename(columns=sanitized_columns, inplace=True)
        
        # Generate CSV
        output = BytesIO()
        df.to_csv(output, index=False, encoding="utf-8")
        output.seek(0)
        
        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=scores.csv"}
        )
    
    except APIError as e:
        raise HTTPException(e.status_code, detail=str(e))
    except Exception as e:
        logger.error(f"Scoring failed: {str(e)}")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Processing failed")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
