# Resume Ranking Tool

The **Resume Ranking Tool** is a FastAPI-based application that automates the process of ranking resumes based on job descriptions. It extracts key criteria from a job description, scores resumes against those criteria, and generates an Excel sheet with the results.

---

## Features

- **Extract Criteria**: Extracts key ranking criteria (e.g., skills, certifications, experience) from a job description (PDF or DOCX).
- **Score Resumes**: Scores multiple resumes against the extracted criteria using NLP techniques.
- **Generate Excel Output**: Produces an Excel sheet with individual scores for each criterion and a total score for each candidate.
- **Swagger UI**: Interactive API documentation for testing endpoints.
- **Easy to Use**: Simple and intuitive interface for uploading files and viewing results.

---

## Technologies Used

- **Backend**: FastAPI
- **Frontend**: HTML, CSS, JavaScript (for testing UI)
- **NLP Libraries**: spaCy, NLTK
- **Text Extraction**: PyPDF2, python-docx
- **Data Processing**: Pandas
- **Excel Generation**: openpyxl

---

## Installation

### Prerequisites

- Python 3.7 or higher
- pip (Python package manager)

### Steps

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/chiragbiradar/resume-ats-assesment.git
   cd resume-ranking-tool
   ```

2. **Set Up a Virtual Environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Download NLTK Data**:
   ```bash
   python -m nltk.downloader punkt
   ```

5. **Run the Application**:
   ```bash
   uvicorn main:app --reload
   ```

6. **Access the Application**:
   - Open your browser and go to `http://127.0.0.1:8000` to use the UI.
   - Access the Swagger UI at `http://127.0.0.1:8000/docs` for API documentation.

---

## Usage

### 1. Extract Criteria from Job Description

- **Endpoint**: `POST /extract-criteria`
- **Input**: Upload a job description file (PDF or DOCX).
- **Output**: A JSON response with the extracted criteria.

**Example**:
```bash
curl -X POST "http://127.0.0.1:8000/extract-criteria" -F "file=@job_description.pdf"
```

### 2. Score Resumes Against Criteria

- **Endpoint**: `POST /score-resumes`
- **Input**: Upload multiple resume files (PDF or DOCX) and provide the extracted criteria.
- **Output**: An Excel sheet with scores for each resume.

**Example**:
```bash
curl -X POST "http://127.0.0.1:8000/score-resumes" \
-F "criteria=Senior Python Developer – AI & Machine Learning" \
-F "criteria=5+ years of experience in Python development" \
-F "files=@resume1.pdf" \
-F "files=@resume2.docx" \
--output scores.xlsx
```

### 3. Web UI

- Access the web UI at `http://127.0.0.1:8000` to:
  - Upload job descriptions and extract criteria.
  - Upload resumes and score them against the criteria.
  - Download the Excel sheet with results.

---

## API Documentation

The API is documented using **Swagger UI**. You can access it at:
```
http://127.0.0.1:8000/docs
```

---

## Example Input and Output

### Input
- **Job Description**: A PDF or DOCX file containing the job description.
- **Resumes**: Multiple PDF or DOCX files containing candidate resumes.

### Output
- **Extracted Criteria**:
  ```json
  {
    "criteria": [
      "5+ years of experience in Python development",
      "Strong knowledge of Machine Learning frameworks (TensorFlow, PyTorch, Scikit-learn)",
      "Must have AWS Certified Machine Learning – Specialty certification"
    ]
  }
  ```

- **Excel Sheet**:
  | Candidate Name | Python Experience | Machine Learning Frameworks | AWS Certification | Total Score |
  |----------------|-------------------|----------------------------|-------------------|-------------|
  | John Doe       | 5                 | 4                          | 5                 | 14          |
  | Jane Smith     | 4                 | 3                          | 4                 | 11          |

---

## Deployment

### Render
1. Create a new **Web Service** on Render.
2. Connect your GitHub repository.
3. Add the following environment variables (if needed):
   - `PYTHON_VERSION`: `3.11`
4. Deploy the application.

### Docker
1. Build the Docker image:
   ```bash
   docker build -t resume-ranking-tool .
   ```
2. Run the container:
   ```bash
   docker run -p 8000:8000 resume-ranking-tool
   ```

---

## Contributing

Contributions are welcome! Please follow these steps:
1. Fork the repository.
2. Create a new branch (`git checkout -b feature/your-feature`).
3. Commit your changes (`git commit -m 'Add some feature'`).
4. Push to the branch (`git push origin feature/your-feature`).
5. Open a pull request.

---


## Contact

For questions or feedback, please contact:
- **Your Name**: [chiragsb16@gmail](mailto:chiragsb16@gmail)
- **GitHub**: [chiragbiradar](https://github.com/chiragbiradar)
