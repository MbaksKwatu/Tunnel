# GITHUB COPILOT – EXECUTE THESE TASKS EXACTLY AS WRITTEN

## 1. Create a file named `runtime.txt` inside the `Tunnel/backend/` directory.
The file must contain exactly:

python-3.11.6

## 2. Open the existing `requirements.txt` inside `Tunnel/backend/`.
If requirements.txt does not exist, create it. Replace its contents with the following pinned versions:

fastapi==0.115.0
uvicorn==0.30.0
pandas==2.2.2
numpy==1.26.4
python-multipart==0.0.9
python-dotenv==1.0.1
openai==1.44.0

## 3. Do not modify any other files.
Do not upgrade pandas, numpy, or install Python 3.13-only packages.

## 4. Create a new commit with message:
"Add runtime.txt for Python 3.11 and pin backend requirements for Render deployment"

## 5. Push the commit to the main branch.
@copilot Execute all tasks in this file exactly as written.
Do not modify any other code. After completing all tasks, create a commit named:
"Add runtime.txt for Python 3.11 and pin backend requirements for Render deployment"
Then push to the main branch.