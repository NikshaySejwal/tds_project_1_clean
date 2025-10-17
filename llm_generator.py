import openai
import json
import base64
from typing import Dict, List, Optional

class CodeGenerator:
    """
    Handles code generation using OpenAI's GPT models.
    Converts natural language briefs into complete web applications.
    """
    
    def __init__(self, api_key: str):
        """
        Initialize the code generator with OpenAI API key.
        
        Args:
            api_key: OpenAI API key for authentication
        """
        self.client = openai.OpenAI(api_key=api_key)
        self.model = "gpt-4"  # Use GPT-4 for better code generation
    
    def generate_app(self, brief: str, attachments: List[Dict] = None, checks: List[str] = None) -> Dict:
        """
        Generate a complete web application from a natural language brief.
        
        Args:
            brief: Natural language description of the desired application
            attachments: List of file attachments (data URIs)
            checks: List of evaluation criteria the app should meet
            
        Returns:
            Dictionary containing generated files (HTML, README, LICENSE)
        """
        if attachments is None:
            attachments = []
        if checks is None:
            checks = []
        
        # Process attachments to extract file content
        attachment_info = self._process_attachments(attachments)
        
        # Create comprehensive prompt for code generation
        prompt = self._create_generation_prompt(brief, attachment_info, checks)
        
        try:
            # Call OpenAI API to generate code
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert web developer. Generate complete, production-ready web applications with proper HTML, CSS, and JavaScript. Always return valid JSON."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.1,  # Low temperature for consistent, reliable code
                max_tokens=4000   # Sufficient tokens for complete applications
            )
            
            # Parse the generated response
            generated_content = response.choices[0].message.content
            
            # Clean up response in case it has markdown formatting
            if "```json" in generated_content:
                generated_content = generated_content.split("```json")[1].split("```")[0]
            elif "```" in generated_content:
                generated_content = generated_content.split("```")[1].split("```")[0]
            
            # Parse JSON response
            result = json.loads(generated_content)
            
            # Validate that all required components are present
            self._validate_generated_content(result)
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            # Return a basic template if generation fails
            return self._get_fallback_template(brief)
        except Exception as e:
            print(f"Code generation error: {e}")
            return self._get_fallback_template(brief)
    
    def _process_attachments(self, attachments: List[Dict]) -> str:
        """
        Process attachment data URIs and extract file content.
        
        Args:
            attachments: List of attachment dictionaries with name and data URI
            
        Returns:
            String describing attachment contents for the prompt
        """
        if not attachments:
            return "No attachments provided."
        
        attachment_descriptions = []
        
        for attachment in attachments:
            name = attachment.get('name', 'unknown')
            data_uri = attachment.get('url', '')
            
            # Parse data URI to extract content
            if data_uri.startswith('data:'):
                try:
                    # Extract MIME type and content
                    header, encoded_content = data_uri.split(',', 1)
                    mime_type = header.split(':')[1].split(';')[0]
                    
                    # Decode base64 content
                    if 'base64' in header:
                        content = base64.b64decode(encoded_content).decode('utf-8')
                    else:
                        content = encoded_content
                    
                    attachment_descriptions.append(f"File '{name}' ({mime_type}):\n{content[:500]}...")  # Limit content length
                    
                except Exception as e:
                    print(f"Error processing attachment {name}: {e}")
                    attachment_descriptions.append(f"File '{name}': Could not process attachment")
        
        return "\n\n".join(attachment_descriptions)
    
    def _create_generation_prompt(self, brief: str, attachment_info: str, checks: List[str]) -> str:
        """
        Create a comprehensive prompt for code generation.
        
        Args:
            brief: Application brief
            attachment_info: Processed attachment information
            checks: List of evaluation criteria
            
        Returns:
            Complete prompt string for the LLM
        """
        checks_text = "\n".join([f"- {check}" for check in checks]) if checks else "None specified"
        
        prompt = f"""
Generate a complete single-page web application based on this specification:

**Application Brief:**
{brief}

**Available Files/Data:**
{attachment_info}

**Evaluation Criteria (the app will be tested against these):**
{checks_text}

**Requirements:**
1. Create a complete HTML file that works standalone
2. Include all CSS inline in <style> tags
3. Include all JavaScript inline in <script> tags
4. Use CDN links for external libraries (Bootstrap, jQuery, etc.) if needed
5. Make the application responsive and professional-looking
6. Implement proper error handling for user interactions
7. Ensure the application meets all specified evaluation criteria
8. Include appropriate meta tags and title
9. Use semantic HTML elements where appropriate

**Output Format:**
Return a JSON object with exactly these keys:
{{
    "html": "complete HTML code including CSS and JS",
    "readme": "comprehensive README.md content explaining the application",
    "license": "standard MIT license content"
}}

The HTML should be a complete, self-contained file that works when opened in a browser.
The README should explain what the app does, how to use it, and how the code works.
The LICENSE should be a standard MIT license.

Important: Return ONLY the JSON object, no additional text or formatting.
"""
        return prompt
    
    def _validate_generated_content(self, content: Dict) -> bool:
        """
        Validate that generated content has all required components.
        
        Args:
            content: Generated content dictionary
            
        Returns:
            True if valid, raises exception if invalid
        """
        required_keys = ['html', 'readme', 'license']
        
        for key in required_keys:
            if key not in content:
                raise ValueError(f"Missing required key: {key}")
            if not content[key] or not isinstance(content[key], str):
                raise ValueError(f"Invalid content for key: {key}")
        
        # Basic validation of HTML content
        html_content = content['html'].lower()
        if '<html' not in html_content or '<body' not in html_content:
            raise ValueError("Generated HTML appears to be incomplete")
        
        return True
    
    def _get_fallback_template(self, brief: str) -> Dict:
        """
        Return a basic template when code generation fails.
        
        Args:
            brief: Original application brief
            
        Returns:
            Dictionary with basic HTML template
        """
        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Generated Application</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
        }}
        .container {{
            background: #f4f4f4;
            padding: 20px;
            border-radius: 8px;
        }}
        h1 {{
            color: #333;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Application Generated</h1>
        <p><strong>Brief:</strong> {brief}</p>
        <p>This is a basic template. The application generation encountered an issue.</p>
        <p>Please check the logs for more information.</p>
    </div>
</body>
</html>"""
        
        readme_template = f"""# Generated Application

## Description
This application was generated based on the following brief:
{brief}

## Usage
Open the index.html file in a web browser to view the application.

## Note
This is a fallback template. The original generation may have encountered issues.
"""
        
        license_template = """MIT License

Copyright (c) 2024 LLM Code Deployment Project

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."""
        
        return {
            'html': html_template,
            'readme': readme_template,
            'license': license_template
        }