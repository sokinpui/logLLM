from logparser.Drain import LogParser
import os
import pandas as pd
import shutil  # Import shutil to copy the file

# Configuration
input_dir = "log/ssh/"  # Input directory (parser reads from here)
output_dir = "./results/"  # Output directory
log_file_name = "SSH.log"  # Just the filename

# Create directories if they don't exist
os.makedirs(input_dir, exist_ok=True)
os.makedirs(output_dir, exist_ok=True)

# --- Ensure the log file is in the input directory ---
# Copy the log file into the input directory the parser expects
input_log_path = os.path.join(input_dir, log_file_name)

# Log format should match the actual structure
# Example for standard SSH: <Month> <Day> <Time> <Host> <Process>[<PID>]: <Content>
# Adjust this format precisely to your log file's structure
log_format = (
    "<Month> <Day> <Time> <Host> <Process>\[<PID>\]: <Content>"  # Example format
)


# Drain parameters
depth = 4  # Depth of the parse tree
st = 0.5  # Similarity threshold
regex_patterns = [
    r"blk_(|-)[0-9]+",  # block id
    r"(/|)([0-9]+\.){3}[0-9]+(:[0-9]+|)(:|)",  # IP address
    # Updated number regex to be more general for integers
    r"(?<=[^A-Za-z0-9])(\-?\+?\d+)(?=[^A-Za-z0-9])|\b\d+\b",
    r"\d{2}:\d{2}:\d{2}",  # Time
    r"\b\w{3}\s+\d{1,2}\b",  # Date like Dec 10
]

# Initialize Drain parser
print("Initializing LogParser...")
parser = LogParser(
    log_format=log_format,
    indir=input_dir,  # Directory where parser looks for log_file_name
    outdir=output_dir,  # Directory where results are saved
    depth=depth,
    st=st,
    rex=regex_patterns,  # Use 'rex' which is the expected parameter name
)

# --- Call the main parse method ---
# This method reads the file, parses it, and writes output files
print(f"Starting parsing for '{log_file_name}'...")
parser.parse(log_file_name)  # Pass the filename (relative to indir)

print("Parsing finished.")
print(f"Check results in '{output_dir}'")

# --- Optional: Load and display results ---
output_file_structured = os.path.join(output_dir, f"{log_file_name}_structured.csv")
output_file_templates = os.path.join(output_dir, f"{log_file_name}_templates.csv")

if os.path.exists(output_file_structured):
    print("\n--- Structured Log Sample ---")
    try:
        df_structured = pd.read_csv(output_file_structured)
        print(df_structured.head())
    except Exception as e:
        print(f"Could not read structured CSV: {e}")

if os.path.exists(output_file_templates):
    print("\n--- Log Templates ---")
    try:
        df_templates = pd.read_csv(output_file_templates)
        print(df_templates)
    except Exception as e:
        print(f"Could not read templates CSV: {e}")
