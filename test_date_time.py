# Test program for the Date/Time Utilities microservice.
# It sends requests to port 5564 and prints each reply.

import json
import time
from datetime import date, timedelta

import zmq

context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.connect("tcp://localhost:5564")

def describe_request(request):
    """Make a short summary of a request so it is easy to read."""
    parts = ["action = " + str(request.get("action"))]
    for key in ("date", "style", "start_date", "end_date", "datetime", "from_tz", "to_tz"):
        if key in request:
            parts.append(key + " = " + str(request[key]))
    return ", ".join(parts)


def describe_reply(reply):
    """Make a short summary of a reply so it is easy to read."""
    if reply["status"] == "error":
        return "status = error, message = " + reply["message"]
    if "days" in reply:
        return "status = ok, days = " + str(reply["days"])
    return "status = ok, result = " + reply["result"]


def ask(request):
    """Send one request, wait for the reply, and return it as a dictionary."""
    print("Sending:  " + describe_request(request))
    socket.send_string(json.dumps(request))
    reply = json.loads(socket.recv_string())
    print("Received: " + describe_reply(reply))
    return reply


def check(name, passed):
    """Print PASS or FAIL for one test."""
    print(("PASS: " if passed else "FAIL: ") + name)
    print()


def days_from_today(number):
    """Return today's date moved by some days, written as MM/DD/YYYY."""
    return (date.today() + timedelta(days=number)).strftime("%m/%d/%Y")


print("Test 1: format a date in the long style")
reply = ask({"action": "format_date", "date": "10/30/2026", "style": "long"})
check("long style gives October 30, 2026",
      reply["status"] == "ok" and reply["result"] == "October 30, 2026")

print("Test 2: format a date that is not written as MM/DD/YYYY")
reply = ask({"action": "format_date", "date": "13/45/2026", "style": "long"})
check("13/45/2026 gives the format error",
      reply["status"] == "error" and reply["message"] == "Date is not valid. Use MM/DD/YYYY")

print("Test 3: format a day that does not exist")
reply = ask({"action": "format_date", "date": "12/32/2026", "style": "long"})
check("12/32/2026 gives the out of range error",
      reply["status"] == "error" and reply["message"] == "Date is not valid. Date out of range")

print("Test 4: format a leap day, then a day that is not a leap day")
reply = ask({"action": "format_date", "date": "02/29/2028", "style": "long"})
leap_ok = reply["status"] == "ok" and reply["result"] == "February 29, 2028"
reply = ask({"action": "format_date", "date": "02/29/2027", "style": "long"})
check("02/29/2028 works and 02/29/2027 gives an error", leap_ok and reply["status"] == "error")

print("Test 5: count the days between two dates")
reply = ask({"action": "duration", "start_date": "10/01/2026", "end_date": "10/30/2026"})
check("10/01/2026 to 10/30/2026 is 29 days", reply["status"] == "ok" and reply["days"] == 29)

print("Test 6: an end date before the start date")
reply = ask({"action": "duration", "start_date": "10/30/2026", "end_date": "10/01/2026"})
check("end date before start date gives the right error",
      reply["status"] == "error" and reply["message"] == "end_date must not be before start_date")

print("Test 7: count days with a day that does not exist")
reply = ask({"action": "duration", "start_date": "12/01/2026", "end_date": "12/32/2026"})
check("12/32/2026 gives the out of range error",
      reply["status"] == "error" and reply["message"] == "Date is not valid. Date out of range")

print("Test 8: speed with 100 years between the dates")
started = time.time()
reply = ask({"action": "duration", "start_date": "01/01/1926", "end_date": "01/01/2026"})
seconds = time.time() - started
print("The reply took " + str(round(seconds, 3)) + " seconds.")
check("100 years answered in 1 second or less", reply["status"] == "ok" and seconds <= 1)

print("Test 9: convert New York time to Berlin time")
reply = ask({"action": "convert_timezone", "datetime": "10/30/2026 14:00",
             "from_tz": "America/New_York", "to_tz": "Europe/Berlin"})
check("14:00 in New York is 19:00 in Berlin",
      reply["status"] == "ok" and reply["result"] == "10/30/2026 19:00")

print("Test 10: convert to a time zone that does not exist")
reply = ask({"action": "convert_timezone", "datetime": "10/30/2026 14:00",
             "from_tz": "America/New_York", "to_tz": "Mars/Base"})
check("Mars/Base gives the unknown time zone error",
      reply["status"] == "error" and reply["message"] == "Unknown time zone: Mars/Base")

print("Test 11: convert to UTC before and after daylight saving time ends")
reply = ask({"action": "convert_timezone", "datetime": "10/31/2026 12:00",
             "from_tz": "America/New_York", "to_tz": "UTC"})
before_ok = reply["status"] == "ok" and reply["result"] == "10/31/2026 16:00"
reply = ask({"action": "convert_timezone", "datetime": "11/01/2026 12:00",
             "from_tz": "America/New_York", "to_tz": "UTC"})
check("16:00 UTC before the change and 17:00 UTC after it",
      before_ok and reply["status"] == "ok" and reply["result"] == "11/01/2026 17:00")

print("Test 12: convert a day that does not exist")
reply = ask({"action": "convert_timezone", "datetime": "12/32/2026 16:00",
             "from_tz": "America/New_York", "to_tz": "UTC"})
check("12/32/2026 gives the out of range error",
      reply["status"] == "error" and reply["message"] == "Date is not valid. Date out of range")

print("Test 13: describe a date 3 days ago")
reply = ask({"action": "relative_date", "date": days_from_today(-3)})
check("3 days before today gives 3 days ago",
      reply["status"] == "ok" and reply["result"] == "3 days ago")

print("Test 14: describe yesterday")
reply = ask({"action": "relative_date", "date": days_from_today(-1)})
check("yesterday gives 1 day ago, not 1 days ago",
      reply["status"] == "ok" and reply["result"] == "1 day ago")

print("Test 15: a good request right after an error")
reply = ask({"action": "banana"})
reply = ask({"action": "format_date", "date": "10/30/2026", "style": "short"})
check("a good request right after an error still works",
      reply["status"] == "ok" and reply["result"] == "Oct 30, 2026")