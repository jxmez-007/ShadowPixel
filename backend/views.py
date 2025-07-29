import os
import openai
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from .models import Resume
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from dotenv import load_dotenv

# Load the .env file from frontend folder
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', 'frontend', '.env'))
openai.api_key = os.getenv('OPENAI_API_KEY')  # Set OpenAI API key

def index(request):
    return render(request, 'index.html')

def uploaded_resumes(request):
    resumes = Resume.objects.all()
    return render(request, 'resumes.html', {'resumes': resumes})

def generate_summary_from_github(username):
    try:
        # Step 1: Get GitHub repos
        url = f'https://api.github.com/users/{username}/repos'
        response = requests.get(url)
        if response.status_code != 200:
            return "GitHub username not found or API limit reached."

        repos = response.json()
        repo_names = [repo['name'] for repo in repos]
        languages = set(repo.get('language') for repo in repos if repo.get('language'))

        # Step 2: AI-based summary using OpenAI
        prompt = (
            f"The GitHub user '{username}' has {len(repos)} repositories: "
            f"{', '.join(repo_names[:5])}... using languages like {', '.join(languages)}. "
            "Write a professional AI summary."
        )

        ai_response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=prompt,
            max_tokens=100,
            temperature=0.7,
        )

        return ai_response.choices[0].text.strip()

    except Exception as e:
        return f"Error generating summary: {str(e)}"

@csrf_exempt
def upload_resume(request):
    if request.method == 'POST':
        uploaded_file = request.FILES.get('resume')
        github_username = request.POST.get('github_username', '')

        if uploaded_file:
            fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'resumes'))
            filename = fs.save(uploaded_file.name, uploaded_file)
            file_url = fs.url(filename)

            ai_summary = generate_summary_from_github(github_username)

            resume = Resume.objects.create(
                resume_file='resumes/' + filename,
                github_username=github_username,
                summary=ai_summary
            )

            return JsonResponse({
                'message': f"Resume '{filename}' uploaded successfully.",
                'github': github_username,
                'summary': ai_summary
            })

        return JsonResponse({'error': 'No file uploaded.'})

    return JsonResponse({'error': 'Only POST allowed.'})