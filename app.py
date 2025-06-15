from flask import Flask, request, jsonify, render_template
import google.generativeai as genai
import os
import json
import re
import logging
from dotenv import load_dotenv
from cachetools import TTLCache

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Setup Gemini API
try:
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel("gemini-1.5-flash-latest")
except Exception as e:
    logger.error(f"Failed to configure Gemini API: {e}")
    print("Error: Invalid Gemini API configuration.")
    exit(1)

# Load and validate product data
PRODUCTS = []
try:
    with open('products.json', 'r', encoding='utf-8') as f:
        raw_products = json.load(f)
    for product in raw_products:
        if not isinstance(product, dict):
            logger.warning("Skipping invalid product entry: not a dictionary")
            continue
        if product.get('category') not in ['smartphone', 'laptop']:
            continue  # Focus on smartphones and laptops
        if not all(key in product for key in ['id', 'name', 'category', 'brand', 'price_inr', 'specs', 'rating']):
            logger.warning(f"Skipping product {product.get('id', 'unknown')}: missing required fields")
            continue
        PRODUCTS.append(product)
except FileNotFoundError:
    logger.error("products.json not found")
    print("Error: products.json not found.")
    exit(1)
except json.JSONDecodeError:
    logger.error("Invalid JSON in products.json")
    print("Error: Invalid JSON in products.json.")
    exit(1)

if not PRODUCTS:
    logger.error("No valid products loaded")
    print("Error: No valid products loaded.")
    exit(1)

# Load prompt from file
def load_prompt(file_path='prompt.md'):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.error("prompt.md not found")
        print("Error: prompt.md not found.")
        exit(1)

PROMPT_TEMPLATE = load_prompt()

# Simple in-memory cache (TTL = 1 hour)
cache = TTLCache(maxsize=100, ttl=3600)

# Extract budget from query
def extract_budget(user_input):
    user_input = user_input.lower().replace('k', '000').replace('thousand', '000')
    patterns = [
        r'(?:under|below|less than)[^\d]*(\d{3,6})',
        r'budget[^\d]*(\d{3,6})',
        r'(\d{1,3}(?:,\d{3})?)\s*(?:inr|rupees)?',
        r'(\d{3,6})\s*(?:inr|rupees)?'
    ]
    for pattern in patterns:
        match = re.search(pattern, user_input)
        if match:
            return int(match.group(1).replace(',', ''))
    return None

# Pre-filter products
def pre_filter_products(user_input):
    user_input = user_input.lower()
    budget = extract_budget (user_input)
    category = 'smartphone' if any(word in user_input for word in ['phone', 'smartphone', 'mobile']) else \
               'laptop' if any(word in user_input for word in ['laptop', 'notebook']) else None

    filtered = []
    for item in PRODUCTS:
        if category and item['category'] != category:
            continue
        if budget and item['price_inr'] > budget:
            continue
        filtered.append(item)
    return filtered if filtered else PRODUCTS  # Fallback to all products if no matches

# Format product for prompt
def format_product(item):
    specs = item.get('specs', {})
    specs_str = f"RAM: {specs.get('RAM', 'N/A')}, Storage: {specs.get('storage', 'N/A')}, " \
                f"Processor: {specs.get('processor', 'N/A')}, Display: {specs.get('display', 'N/A')}, " \
                f"Battery: {specs.get('battery', 'N/A')}, Camera: {specs.get('camera', 'N/A')}"
    return f"- {item['name']} ({item['brand']})\n  ₹{item['price_inr']} | ⭐ {item['rating']} | Tier: {item.get('tier', 'N/A')}\n  Specs: {specs_str}"

# Home page
@app.route("/")
def index():
    return render_template("index.html")

# Ask route
@app.route("/ask", methods=["POST"])
def ask():
    # Validate request
    if not request.is_json:
        logger.warning("Invalid request format: not JSON")
        return jsonify({"reply": "Invalid request format."}), 400
    data = request.get_json()
    user_message = data.get("message", "")
    if not user_message or not isinstance(user_message, str):
        logger.warning("Invalid user message")
        return jsonify({"reply": "Please provide a valid query."}), 400

    logger.info(f"Received query: {user_message}")

    # Check for non-product queries
    if not any(keyword in user_message.lower() for keyword in ['phone', 'smartphone', 'mobile', 'laptop', 'notebook', 'gaming', 'coding', 'student', 'camera', 'battery']):
        logger.info("Non-product query detected")
        reply = "I’m your tech advisor for phones and laptops! Ask me something like ‘best gaming phone under ₹50K’ or ‘laptop for work under ₹60K’."
        cache_key = user_message.lower()
        cache[cache_key] = reply
        return jsonify({"reply": reply})

    # Check cache
    cache_key = user_message.lower()
    if cache_key in cache:
        logger.info(f"Cache hit for query: {cache_key}")
        return jsonify({"reply": cache[cache_key]})
    else:
        logger.info(f"Cache miss for query: {cache_key}")

    # Pre-filter products
    filtered_products = pre_filter_products(user_message)
    product_summary = "\n".join(format_product(item) for item in filtered_products)

    # Construct prompt
    prompt = PROMPT_TEMPLATE.replace("{user_message}", user_message).replace("{product_summary}", product_summary)

    # Call Gemini
    try:
        response = model.generate_content(prompt)
        reply = response.text.strip()
        word_count = len(reply.split())
        if word_count > 350 or not reply or not any(keyword in reply.lower() for keyword in ['recommended', 'product', 'pros', 'cons']):
            logger.warning(f"Invalid Gemini response: {word_count} words or missing keywords")
            reply = "Sorry, I couldn't find suitable products. Try rephrasing your query (e.g., 'gaming laptop under ₹80000')."
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        reply = "Sorry, something went wrong. Please try again later."

    # Cache response
    cache[cache_key] = reply

    return jsonify({"reply": reply})

if __name__ == "__main__":
    app.run(debug=False)