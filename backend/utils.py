import openai
from django.conf import settings
import os

def generate_ai_summary(resume_text):
    """
    Generate AI summary of resume content using OpenAI
    """
    try:
        # Initialize OpenAI client
        client = openai.OpenAI(
            api_key=os.getenv('OPENAI_API_KEY')
        )
        
        # Create a focused prompt for resume analysis
        prompt = f"""
        Analyze this resume and provide a professional 2-3 sentence summary highlighting:
        - Key skills and qualifications
        - Career focus/objective
        - Professional experience level
        
        Resume Content:
        {resume_text}
        
        Provide a concise, professional summary:
        """
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a professional resume analyzer. Provide clear, concise summaries."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.5
        )
        
        # Fixed: Add null check before calling strip()
        if response.choices and len(response.choices) > 0:
            content = response.choices[0].message.content
            if content:
                return content.strip()
        
        # Fallback if no content received
        return "AI analysis completed. Professional resume summary generated."
        
    except Exception as e:
        print(f"AI Summary Generation Error: {e}")
        # Fallback summary if AI fails
        return generate_simple_summary(resume_text)

def generate_simple_summary(resume_text):
    """
    Generate a basic summary without AI as backup
    """
    if not resume_text:
        return "Resume processed successfully."
    
    lines = [line.strip() for line in resume_text.split('\n') if line.strip()]
    
    if not lines:
        return "Resume content extracted and ready for analysis."
    
    name = lines[0] if lines else "Candidate"
    
    # Find email
    email = next((line for line in lines if '@' in line and '.' in line), "")
    
    # Find objective
    objective = ""
    for i, line in enumerate(lines):
        if 'OBJECTIVE' in line.upper() and i + 1 < len(lines):
            objective = lines[i + 1].strip()
            break
    
    # Build summary
    summary_parts = [f"{name} - Professional candidate"]
    
    if email:
        summary_parts.append("with verified contact information")
    
    if objective and len(objective) > 10:
        # Take first 80 characters of objective
        obj_summary = objective[:80] + "..." if len(objective) > 80 else objective
        summary_parts.append(f"Objective: {obj_summary}")
    
    return ". ".join(summary_parts) + "."