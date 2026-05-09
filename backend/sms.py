import os
from twilio.rest import Client

def send_sms(phone: str, message: str) -> dict:
    """Send an SMS via Twilio. Returns a dict compatible with the previous format."""
    
    # Get credentials from environment variables
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_PHONE_NUMBER")

    try:
        client = Client(account_sid, auth_token)
        
        # Send the message
        msg = client.messages.create(
            body=message,
            from_=from_number,
            to=phone
        )
        
        # Format response to match your existing logic
        response = {
            "success": True,
            "sid": msg.sid,
            "status": msg.status
        }
        print(response)
        return response

    except Exception as e:
        error_msg = str(e)
        print("error", error_msg)
        return {"success": False, "error": error_msg}
