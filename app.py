from flask import Flask, render_template, request, jsonify
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import io
import base64
import os
import google.generativeai as genai
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure Gemini API
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
print("Using API Key:", GOOGLE_API_KEY)  # Debug print
genai.configure(api_key=GOOGLE_API_KEY)

# Set up the model
model = genai.GenerativeModel('gemini-2.0-flash')

# List of common Chinese characters (simplified)
chinese_chars = [
    "一", "二", "三", "四", "五", "六", "七", "八", "九", "十",
    "人", "口", "日", "月", "水", "火", "木", "金", "土", "山",
    "大", "小", "中", "上", "下", "左", "右", "天", "地", "心"
]

@app.route('/')
def index():
    # Select a random character
    current_char = random.choice(chinese_chars)
    return render_template('index.html', character=current_char)

@app.route('/check_drawing', methods=['POST'])
def check_drawing():
    try:
        data = request.get_json()
        drawn_points = data.get('points', [])
        target_char = data.get('target_char', '')
        
        # Calculate score based on similarity
        score = calculate_score(drawn_points, target_char)
        
        return jsonify({'score': score})
    except Exception as e:
        print(f"Error in check_drawing: {str(e)}")
        return jsonify({'error': str(e)}), 500

def calculate_score(drawn_points, target_char):
    if not drawn_points or len(drawn_points) < 10:
        return 0
    
    try:
        # Create a reference image of the target character
        reference_img = create_reference_image(target_char)
        
        # Create a drawn image from the points
        drawn_img = create_drawn_image(drawn_points)
        
        # Compare the two images
        similarity = compare_images(reference_img, drawn_img)
        
        # Convert similarity to a score between 0 and 100
        score = int(similarity * 100)
        
        return score
    except Exception as e:
        print(f"Error in calculate_score: {str(e)}")
        # Return a default score in case of error
        return 50

def create_reference_image(char):
    # Create a blank image with white background
    img = Image.new('RGB', (400, 400), color='white')
    draw = ImageDraw.Draw(img)
    
    # Try to load a Chinese font, fall back to default if not available
    font = None
    font_paths = [
        "/System/Library/Fonts/PingFang.ttc",  # macOS
        "/System/Library/Fonts/STHeiti Light.ttc",  # macOS
        "NotoSansCJK-Regular.ttc",
        "SimHei.ttf",
        "SimSun.ttf"
    ]
    
    for font_path in font_paths:
        try:
            font = ImageFont.truetype(font_path, 200)
            break
        except IOError:
            continue
    
    if font is None:
        font = ImageFont.load_default()
    
    # Draw the character in the center
    try:
        # For newer Pillow versions
        text_width, text_height = font.getsize(char)
    except AttributeError:
        # For older Pillow versions
        text_width, text_height = draw.textsize(char, font=font)
    
    position = ((400 - text_width) / 2, (400 - text_height) / 2)
    draw.text(position, char, font=font, fill='black')
    
    return img

def create_drawn_image(points):
    # Create a blank image with white background
    img = Image.new('RGB', (400, 400), color='white')
    draw = ImageDraw.Draw(img)
    
    # Draw lines between consecutive points
    if len(points) > 1:
        for i in range(len(points) - 1):
            draw.line([points[i], points[i+1]], fill='black', width=5)
    
    return img

def compare_images(img1, img2):
    # Convert images to numpy arrays
    arr1 = np.array(img1)
    arr2 = np.array(img2)
    
    # Convert to grayscale if needed
    if len(arr1.shape) == 3:
        arr1 = np.mean(arr1, axis=2).astype(np.uint8)
    if len(arr2.shape) == 3:
        arr2 = np.mean(arr2, axis=2).astype(np.uint8)
    
    # Normalize arrays to 0-1 range
    arr1 = arr1 / 255.0
    arr2 = arr2 / 255.0
    
    # Calculate similarity using structural similarity index
    # This is a simplified version - in a real app you'd use scikit-image's SSIM
    diff = np.abs(arr1 - arr2)
    similarity = 1 - np.mean(diff)
    
    return similarity

@app.route('/api/gemini', methods=['POST'])
def gemini_api():
    try:
        data = request.json
        starting_city = data.get('startingCity', '')
        activities = data.get('activities', [])
        budget = data.get('budget', 'medium')
        regions = data.get('regions', [])
        start_date = data.get('startDate', '')
        end_date = data.get('endDate', '')
        
        if not starting_city:
            return jsonify({"error": "Starting city is required"}), 400
        
        print("Processing request for starting city:", starting_city)  # Debug log
        
        # First, correct the starting city
        city_correction_prompt = f"""
        Please correct this city name to its proper format (city, country):
        {starting_city}
        Return ONLY the corrected city name in the format "City, Country" with proper capitalization.
        """
        city_response = model.generate_content(city_correction_prompt)
        corrected_city = city_response.text.strip()
        print("Corrected city:", corrected_city)  # Debug log
        
        # Construct the main prompt for recommendations
        prompt = f"""
        I'm planning a vacation with the following preferences:
        - Starting from: {corrected_city}
        - Activities: {', '.join(activities)}
        - Budget: {budget}
        - Preferred regions: {', '.join(regions) if regions else 'No specific regions'}
        - Travel dates: {start_date} to {end_date}
        
        Please recommend 5-8 major cities that would be perfect for this vacation.
        For each city, provide the following information in JSON format:
        {{
            "cities": [
                {{
                    "name": "City, Country",
                    "activities": ["activity1", "activity2", ...],
                    "budget": "low/medium/high",
                    "bestSeasons": ["spring", "summer", "fall", "winter"],
                    "description": "Brief description of the city",
                    "continent": "Continent name",
                    "country": "Country name",
                    "coordinates": {{"lat": latitude, "lng": longitude}}
                }}
            ],
            "travelTimes": {{
                "City1, Country1": {{
                    "City2, Country2": {{
                        "primaryMode": "airplane/train/bus/car",
                        "airplane": hours,
                        "train": hours or null,
                        "bus": hours or null,
                        "car": hours or null
                    }}
                }}
            }}
        }}
        
        Important requirements:
        1. Do NOT include {corrected_city} in the recommended cities
        2. Ensure all cities are well-distributed geographically
        3. Each city must offer at least 2 of the requested activities
        4. For travel times between cities:
           - For international routes (between different countries or continents), ALWAYS use "airplane" as the primaryMode
           - For domestic routes, determine the most common/primary transportation mode
           - Then provide the travel time for that mode
           - Also include other available modes with their times
           - Use null for modes that aren't available between those cities
        5. For each city, determine if it's luxury (high), moderate (medium), or budget-friendly (low)
        6. Make sure the response is in valid JSON format
        """
        
        print("Calling Gemini API with prompt:", prompt)  # Debug log
        
        # Generate content with Gemini
        response = model.generate_content(prompt)
        
        print("Gemini API response:", response.text)  # Debug log
        
        # Return the response
        return jsonify({"response": response.text})
    
    except Exception as e:
        print("Error in Gemini API:", str(e))  # Debug log
        import traceback
        traceback.print_exc()  # Print full error traceback
        return jsonify({"error": f"Gemini API error: {str(e)}"}), 500

def process_travel_times(travel_times_str):
    """Process travel times string into a structured format."""
    try:
        # Parse the travel times string into a dictionary
        travel_times = json.loads(travel_times_str)
        
        # Ensure each route has a primaryMode
        for from_city, routes in travel_times.items():
            for to_city, modes in routes.items():
                if not isinstance(modes, dict):
                    continue
                    
                # If no primaryMode is specified, use the first available mode
                if 'primaryMode' not in modes:
                    available_modes = [mode for mode in modes.keys() if mode != 'primaryMode' and mode != 'popularity']
                    if available_modes:
                        modes['primaryMode'] = available_modes[0]
                    else:
                        modes['primaryMode'] = 'airplane'  # Default to airplane if no modes available
                
                # Ensure all time values are numeric
                for mode, time in modes.items():
                    if mode != 'primaryMode' and mode != 'popularity':
                        try:
                            modes[mode] = float(time) if time is not None else None
                        except (ValueError, TypeError):
                            modes[mode] = None  # Use None for invalid values
                
                # Ensure popularity values are numeric
                if 'popularity' in modes:
                    for mode, percentage in modes['popularity'].items():
                        try:
                            modes['popularity'][mode] = float(percentage) if percentage is not None else None
                        except (ValueError, TypeError):
                            modes['popularity'][mode] = None  # Use None for invalid values
                else:
                    # Create a default popularity object if missing
                    modes['popularity'] = {}
                    for mode in ['airplane', 'train', 'bus', 'car', 'ferry']:
                        if mode in modes and modes[mode] is not None:
                            # If the mode is available, set a default popularity
                            modes['popularity'][mode] = 100.0 if mode == modes['primaryMode'] else 0.0
                        else:
                            modes['popularity'][mode] = None
                            
        return travel_times
    except json.JSONDecodeError:
        print("Error decoding travel times JSON")
        return {}
    except Exception as e:
        print(f"Error processing travel times: {str(e)}")
        return {}

@app.route('/get_travel_times', methods=['POST'])
def get_travel_times():
    try:
        data = request.get_json()
        cities = data.get('cities', [])
        starting_city = data.get('startingCity', '')
        
        if not cities:
            return jsonify({"error": "No cities provided"}), 400
            
        # Add starting city to the list if provided
        if starting_city:
            cities.insert(0, starting_city)
            
        # Generate travel times using Gemini API
        travel_times_str = generate_travel_times(cities)
        
        # Process the travel times to ensure proper format
        travel_times = process_travel_times(travel_times_str)
        
        return jsonify({"travel_times": travel_times})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def generate_travel_times(cities):
    """Generate travel times between cities using Gemini API."""
    try:
        # Construct the prompt
        prompt = f"""For each pair of cities in the following list, determine the most popular transportation mode and travel time between them. 
        Format the response as a JSON object where each city pair is represented as:
        {{
            "from_city": {{
                "to_city": {{
                    "primaryMode": "mode_name",
                    "airplane": hours or null,
                    "train": hours or null,
                    "bus": hours or null,
                    "car": hours or null,
                    "ferry": hours or null,
                    "popularity": {{
                        "airplane": percentage or null,
                        "train": percentage or null,
                        "bus": percentage or null,
                        "car": percentage or null,
                        "ferry": percentage or null
                    }}
                }}
            }}
        }}
        
        Available transportation modes: airplane, train, bus, car, ferry
        
        Cities: {', '.join(cities)}
        
        For each route:
        1. Determine which transportation mode is most popular between these cities
        2. Set that as the primaryMode
        3. Provide the travel time for that mode
        4. Also include other available modes with their times
        5. For each mode, provide a rough percentage of travelers who use that mode (null if not applicable)
        6. If a route is not possible with a particular mode, use null for both the time and popularity
        7. For international routes, consider both airplane and train options if applicable
        8. For domestic routes, consider all relevant transportation options
        """
        
        # Generate response from Gemini
        response = model.generate_content(prompt)
        
        # Extract the JSON response
        travel_times = response.text
        
        return travel_times
    except Exception as e:
        print(f"Error generating travel times: {str(e)}")
        return "{}"

if __name__ == '__main__':
    app.run(debug=True, port=5007) 