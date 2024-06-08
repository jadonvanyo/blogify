from .models import SummaryPost
from decouple import config
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings
from pytube import YouTube
import assemblyai as aai
import json
import openai
import os


# Create your views here
@login_required
def index(request):
    return render(request, 'index.html')

@csrf_exempt
def generate_blog(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            yt_link = data['link']
        except (KeyError, json.JSONDecodeError):
            return JsonResponse({'error': 'Invalid data sent'}, status=400)
        
        # get yt title
        title = yt_title(yt_link)
        
        # get transcript
        transcription = get_transcription(yt_link)
        if not transcription:
            return JsonResponse({'error': "Failed to get transcript"}, status=500)
        
        # use OpenAi to generate a summary
        summary = generate_summary_from_transcription(transcription)
        if not summary:
            return JsonResponse({'error': "Failed to generate summary"}, status=405)
        
        # save summary to database
        new_summary = SummaryPost.objects.create(
            user=request.user,
            youtube_title=title,
            youtube_link=yt_link,
            generated_content=summary
        )
        new_summary.save()
        
        # return summary as a response
        return JsonResponse({'content': summary})
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
def yt_title(link):
    yt = YouTube(link)
    title = yt.title
    return title

def download_audio(link):
    yt = YouTube(link)
    video = yt.streams.filter(only_audio=True).first()
    out_file = video.download(output_path=settings.MEDIA_ROOT)
    base, ext = os.path.splitext(out_file)
    new_file = base + '.mp3'
    os.rename(out_file, new_file)
    return new_file

def get_transcription(link):
    audio_file = download_audio(link)
    aai_api_key = config('ASSEMBLY_AI_API_KEY')
    aai.settings.api_key = f"{aai_api_key}"
    
    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(audio_file)
    
    return transcript.text

def generate_summary_from_transcription(transcription):
    openai.api_key = f"{config('OPENAI_API_KEY')}"
    
    prompt = f"Write a summary of the following transcript from a YouTube video. \nTranscript: '''\n{transcription}\n'''"
    
    # TODO: Update this to messages and 
    response = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500
    )
    
    generated_content = response.choices[0].message.content.strip()
    
    return generated_content

def summary_list(request):
    summaries = SummaryPost.objects.filter(user=request.user)
    return render(request, "all-blogs.html", {'summaries': summaries})

def user_login(request):
    if request.method == "POST":
        # Get user entered info
        username = request.POST['username']
        password = request.POST['password']
        
        # Authenticate the user
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('/')
        else:
            error_message = "Invalid username or password"
            return render(request, 'login.html', {'error_message':error_message})
    return render(request, 'login.html')

def user_signup(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        repeatPassword = request.POST['repeatPassword']
        
        # Determine if password and repeat password do not match
        if password != repeatPassword:
            error_message = 'Password does not match'
            return render(request, 'signup.html', {'error_message':error_message})
        # Try to create a user
        try: 
            user = User.objects.create_user(username, email, password)
            user.save()
            login(request, user)
            return redirect('/')
        except:
            error_message = 'Error creating account'
            return render(request, 'signup.html', {'error_message':error_message})
    
    # Return the signup page for get request
    return render(request, 'signup.html')

def user_logout(request):
    logout(request)
    return redirect('/')