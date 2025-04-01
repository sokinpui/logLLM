from parse import parse

# Define the log line
log_line = "Dec 10 07:28:10 LabSZ sshd[24251]: pam_unix(sshd:auth): authentication failure; logname= uid=0 euid=0 tty=ssh ruser= rhost=112.95.230.3 user=root"

# Define the parsing pattern
pattern = "{timestamp} {target} {event}"

# Parse the log line
result = parse(pattern, log_line)

# Convert to dictionary and print
if result:
    parsed_dict = result.named
    print("Parsed Dictionary:")
    print(parsed_dict)
else:
    print("Parsing failed")
