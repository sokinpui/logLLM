from pygrok import Grok
import json

# Your log data as a Python dictionary (or loaded from a JSON file/string)
log_data_input = {
    "apache": [
        "[Mon Feb 27 17:32:59 2006] [error] [client 136.159.45.9] Directory index forbidden by rule: /var/www/html/",
        "[Mon Feb 27 17:44:14 2006] [error] [client 216.187.87.166] Directory index forbidden by rule: /var/www/html/",
        "[Mon Feb 27 18:01:24 2006] [error] [client 219.95.66.42] Directory index forbidden by rule: /var/www/html/",
        "[Mon Feb 27 18:43:18 2006] [error] [client 24.70.5.136] Directory index forbidden by rule: /var/www/html/",
        "[Mon Feb 27 21:17:17 2006] [error] [client 136.142.64.221] Directory index forbidden by rule: /var/www/html/",
        "[Mon Feb 27 21:56:11 2006] [error] [client 220.225.166.39] Directory index forbidden by rule: /var/www/html/",
        "[Tue Feb 28 00:45:58 2006] [error] [client 206.125.60.10] Directory index forbidden by rule: /var/www/html/",
        "[Tue Feb 28 00:46:47 2006] [error] [client 203.186.238.253] Directory index forbidden by rule: /var/www/html/",
        "[Tue Feb 28 03:04:53 2006] [error] [client 69.39.5.163] Directory index forbidden by rule: /var/www/html/",
        "[Tue Feb 28 03:49:01 2006] [error] [client 218.22.153.242] Directory index forbidden by rule: /var/www/html/%",
        # Adding a line without client IP to test the optional part, based on your first request's logs
        "[Tue Dec 06 12:24:26 2005] [notice] workerEnv.init() ok /etc/httpd/conf/workers2.properties",
    ]
}

apache_log_lines = log_data_input["apache"]

# Your Grok pattern
# I've added a space before %{GREEDYDATA:message} to ensure the message doesn't start with a space.
# Using a raw string (r"...") is good practice for patterns.
grok_pattern = r"\[%{DAY:day} %{MONTH:month} %{MONTHDAY:monthday} %{TIME:time} %{YEAR:year}\] \[%{LOGLEVEL:loglevel}\](?: \[client %{IP:client}\])? %{GREEDYDATA:message}"

# Initialize Grok with the pattern
grok = Grok(grok_pattern)

parsed_results = []

for line in apache_log_lines:
    # Parse the log line
    parsed_data = grok.match(line)
    if parsed_data:
        # If you want a single timestamp field like in your initial request, you can construct it:
        # parsed_data['timestamp'] = f"{parsed_data['day']} {parsed_data['month']} {parsed_data['monthday']} {parsed_data['time']} {parsed_data['year']}"
        parsed_results.append(parsed_data)
    else:
        print(f"Could not parse line: {line}")

# Print the parsed results
for result in parsed_results:
    print(json.dumps(result, indent=4))

print(
    f"\nSuccessfully parsed {len(parsed_results)} out of {len(apache_log_lines)} log lines."
)
