# Date/Time Utilities microservice.
# It waits for one request at a time on port 5564 (ZeroMQ), then sends back one reply

import json
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import zmq

PORT = 5564

BAD_FORMAT = "Date is not valid. Use MM/DD/YYYY"
OUT_OF_RANGE = "Date is not valid. Date out of range"
BAD_TIME = "Time is not valid. Use HH:MM (24 hour clock)"


def error_reply(message):
    """Build the reply used whenever something is wrong."""
    return {"status": "error", "message": message}

def result_reply(result):
    """Build the reply used when format_date, convert_timezone, or relative_date worked."""
    return {"status": "ok", "result": result}

def days_reply(days):
    """Build the reply used when duration worked."""
    return {"status": "ok", "days": days}

def describe_request(request):
    """Make a short summary of a request for the message in the window."""
    if not isinstance(request, dict):
        return "something that is not a request"
    parts = ["action = " + str(request.get("action"))]
    for key in ("date", "style", "start_date", "end_date", "datetime", "from_tz", "to_tz"):
        if key in request:
            parts.append(key + " = " + str(request[key]))
    return ", ".join(parts)

def describe_reply(reply):
    """Make a short summary of a reply for the message in the window."""
    if reply["status"] == "error":
        return "status = error, message = " + reply["message"]
    if "days" in reply:
        return "status = ok, days = " + str(reply["days"])
    return "status = ok, result = " + reply["result"]

 
def find_missing(request, names):
    """Return the name of the first required field that is missing, or None."""
    for name in names:
        if not isinstance(request.get(name), str) or request.get(name) == "":
            return name
    return None

def date_problem(text):
    """Return an error message if text is not a real MM/DD/YYYY date, or None if it is fine."""
    if not re.fullmatch(r"\d{2}/\d{2}/\d{4}", text):
        return BAD_FORMAT
    month = int(text[0:2])
    if month < 1 or month > 12:
        # A month over 12 usually means someone sent DD/MM/YYYY
        return BAD_FORMAT
    try:
        datetime.strptime(text, "%m/%d/%Y")
    except ValueError:
        # The month is fine but that day does not exist, such as 12/32 or 02/29/2027
        return OUT_OF_RANGE
    return None

def read_date(text):
    """Turn MM/DD/YYYY text into a date. Only call this after date_problem says it is fine."""
    return datetime.strptime(text, "%m/%d/%Y").date()
 
 
def time_problem(text):
    """Return an error message if text is not a real HH:MM time, or None if it is fine."""
    if not re.fullmatch(r"\d{2}:\d{2}", text):
        return BAD_TIME
    if int(text[0:2]) > 23 or int(text[3:5]) > 59:
        return BAD_TIME
    return None

def find_zone(name):
    """Return the time zone with this name, or None if there is no such time zone."""
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return None

def plural_days(number):
    """Return "1 day" or "3 days"."""
    if number == 1:
        return "1 day"
    return str(number) + " days"

def handle_format_date(request):
    missing = find_missing(request, ["date", "style"])
    if missing:
        return error_reply("Missing required field: " + missing)
    problem = date_problem(request["date"])
    if problem:
        return error_reply(problem)
 
    when = read_date(request["date"])
    if request["style"] == "long":
        return result_reply(when.strftime("%B") + " " + str(when.day) + ", " + str(when.year))
    if request["style"] == "short":
        return result_reply(when.strftime("%b") + " " + str(when.day) + ", " + str(when.year))
    return error_reply('style must be "long" or "short"')


def handle_duration(request):
    missing = find_missing(request, ["start_date", "end_date"])
    if missing:
        return error_reply("Missing required field: " + missing)
    problem = date_problem(request["start_date"]) or date_problem(request["end_date"])
    if problem:
        return error_reply(problem)
 
    start = read_date(request["start_date"])
    end = read_date(request["end_date"])
    if end < start:
        return error_reply("end_date must not be before start_date")
    return days_reply((end - start).days)

def handle_convert_timezone(request):
    missing = find_missing(request, ["datetime", "from_tz", "to_tz"])
    if missing:
        return error_reply("Missing required field: " + missing)
 
    parts = request["datetime"].split()
    if len(parts) != 2:
        return error_reply("Datetime is not valid. Use MM/DD/YYYY HH:MM")
    problem = date_problem(parts[0]) or time_problem(parts[1])
    if problem:
        return error_reply(problem)
 
    from_zone = find_zone(request["from_tz"])
    if from_zone is None:
        return error_reply("Unknown time zone: " + request["from_tz"])
    to_zone = find_zone(request["to_tz"])
    if to_zone is None:
        return error_reply("Unknown time zone: " + request["to_tz"])
 
    start = datetime.strptime(request["datetime"], "%m/%d/%Y %H:%M").replace(tzinfo=from_zone)
    converted = start.astimezone(to_zone)
    return result_reply(converted.strftime("%m/%d/%Y %H:%M"))

def handle_relative_date(request):
    missing = find_missing(request, ["date"])
    if missing:
        return error_reply("Missing required field: " + missing)
    problem = date_problem(request["date"])
    if problem:
        return error_reply(problem)
 
    difference = (date.today() - read_date(request["date"])).days
    if difference == 0:
        return result_reply("today")
    if difference > 0:
        return result_reply(plural_days(difference) + " ago")
    return result_reply("in " + plural_days(-difference))

def handle_request(request):
    """Look at one request and return the reply (a dictionary)."""
    if not isinstance(request, dict):
        return error_reply("Request must be a JSON object")
 
    action = request.get("action")
    if action == "format_date":
        return handle_format_date(request)
    if action == "duration":
        return handle_duration(request)
    if action == "convert_timezone":
        return handle_convert_timezone(request)
    if action == "relative_date":
        return handle_relative_date(request)
    return error_reply("Unknown action: " + str(action))

def main():
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind("tcp://*:" + str(PORT))
    print("Date/Time Utilities microservice is running on port " + str(PORT))
    print("Press the Control key and the C key together to stop it.")
 
    try:
        while True:
            # Wait up to half a second for a request. This short wait is what
            # lets Control and C stop the program on Windows.
            if socket.poll(500) == 0:
                continue
            message = socket.recv_string()
            try:
                request = json.loads(message)
                print("Received a request: " + describe_request(request))
                reply = handle_request(request)
            except json.JSONDecodeError:
                print("Received a request that is not valid JSON text")
                reply = error_reply("Request must be valid JSON text")
            except Exception as problem:
                reply = error_reply("Something went wrong: " + str(problem))
            socket.send_string(json.dumps(reply))
            print("Sent a reply: " + describe_reply(reply))
    except KeyboardInterrupt:
        print("Date/Time Utilities microservice stopped.")
    finally:
        socket.close()
        context.term()

if __name__ == "__main__":
    main()