from openai.types.chat import ChatCompletionUserMessageParam

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    session,
)
from flask_session import Session
import openai
import os
import base64
import re
import requests

from twilio.rest import Client

app = Flask(__name__)

# Session configuration
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

openai.api_key = "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"
app.secret_key = "supersecretkey"

# Twilio credentials
account_sid = "ACe9e96fffa3a05bff45cd3c9749d73427"
auth_token = "b45a3727d3e2b7ea6fb54811b6854e6e"
twilio_phone_number = "+18557270309"  # Your Twilio phone number
user_phone_number = "+15184291145"    # The user's phone number for testing

# Open and read txt file, create variable for the contents
with open("topic_prompts/directive.txt", "r") as file:
    additional_context = file.read()

# Function to extract context from the assistant's response


def extract_fire_alert_from_response(response_text):
    return response_text.strip()

# Function to determine the fire risk level from the assistant's response


def determine_fire_risk_level(fire_alert_context):
    if "Warning: Fire Emergency Detected" in fire_alert_context:
        return "imminent fire emergency"
    elif "Caution: High Fire Risk" in fire_alert_context:
        return "high-risk fire hazard"
    elif "Reminder: Fire Safety Notice" in fire_alert_context:
        return "moderate fire hazard"
    else:
        return "no fire hazard"

# Function to send SMS via Twilio


def send_sms_via_twilio(to_number, from_number, body):
    url = f'https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json'
    data = {
        'To': to_number,
        'From': from_number,
        'Body': body
    }
    try:
        response = requests.post(
            url, data=data, auth=(account_sid, auth_token))
        response.raise_for_status()  # Raise an exception for HTTP errors
        app.logger.info(f"SMS sent: {response.json()['sid']}")
    except requests.exceptions.RequestException as e:
        app.logger.error(f"An error occurred while sending SMS: {e}")


@app.route("/")
def home():
    return render_template("home.html")

# New route to process images from the webcam


@app.route("/process_image", methods=["POST"])
def process_image():
    data = request.get_json()
    image_data = data.get("image_data")

    if not image_data:
        return jsonify({"error": "No image data provided."}), 400

    # Remove the data URL prefix to get the base64-encoded image data
    image_base64 = re.sub('^data:image/.+;base64,', '', image_data)

    # Prepare the image data for the OpenAI API
    image_url = f"data:image/jpeg;base64,{image_base64}"

    # Construct the messages as per OpenAI's vision API
    messages: list[ChatCompletionUserMessageParam] = [
        ChatCompletionUserMessageParam(
            role="user",
            content=[
                {
                    "type": "text",
                    "text": (
                        f"You look for poor posture / let users know when they need to improve their posture while working. "
                        f"Use the following context to guide your response:\n\n{additional_context}"
                    )
                },
                {
                    "type": "image_url",
                    "image_url": {"url": image_url}
                }
            ]
        )
    ]

    try:
        # Call the OpenAI API with the image
        response = openai.chat.completions.create(
            model="gpt-4-turbo-2024-04-09",
            messages=messages,
            max_tokens=500
        )
        # Extract the assistant's response
        gpt_response = response.choices[0].message.content

        # Extract fire alert context from the response
        fire_alert_context = extract_fire_alert_from_response(gpt_response)

        # Store context in the session
        session["fire_alert_context"] = fire_alert_context

        # Determine the fire risk level
        risk_level = determine_fire_risk_level(fire_alert_context)

        # Decide whether to send SMS
        if risk_level in ["imminent fire emergency", "high-risk fire hazard", "moderate fire hazard"]:
            # Send SMS
            send_sms_via_twilio(
                to_number=user_phone_number,
                from_number=twilio_phone_number,
                body=fire_alert_context
            )

        return jsonify({"context": fire_alert_context})
    except Exception as e:
        app.logger.error(f"An error occurred: {e}")
        return jsonify({"error": str(e)}), 500

# Clear session route


@app.route("/clear_session", methods=["GET"])
def clear_session():
    # Clear the session
    session.clear()
    return jsonify({"status": "session cleared"})


if __name__ == "__main__":
    app.run(debug=True, port=8080)
