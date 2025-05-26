from pygrok import Grok

pattern_ok = r"\[%{DAY:day} %{MONTH:month} %{MONTHDAY:monthday} %{TIME:time} %{YEAR:year}\] \[%{LOGLEVEL:loglevel}\](?: \[client %{IP:client}\])? %{GREEDYDATA:message}"
pattern_with_newline = pattern_ok + "\n"  # Add a newline
log_line = "[Mon Feb 27 17:32:59 2006] [error] [client 136.159.45.9] Directory index forbidden by rule: /var/www/html/"

grok_ok = Grok(pattern_ok)
grok_with_newline = Grok(pattern_with_newline)

print(f"Pattern without newline match: {grok_ok.match(log_line)}")
# Output: {'day': 'Mon', ...}

print(f"Pattern with newline match: {grok_with_newline.match(log_line)}")
# Output: None
