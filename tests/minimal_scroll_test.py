# minimal_scroll_test.py
import os
import logging
from elasticsearch import Elasticsearch

# Enable verbose logging
logging.basicConfig(level=logging.DEBUG) # Basic config for simplicity
logging.getLogger("elasticsearch").setLevel(logging.DEBUG)
logging.getLogger("urllib3").setLevel(logging.DEBUG)

print("Attempting to connect to Elasticsearch...")
try:
    # Ensure NO_PROXY is set in your environment before running this!
    print(f"NO_PROXY is set to: {os.environ.get('NO_PROXY')}")
    es_client = Elasticsearch(
        ["http://localhost:9200"],
        request_timeout=60 # Reasonable timeout
    )
    print("Connection object created.")
    es_client.ping() # Verify connection
    print("Ping successful.")

    index_name = "log_openstack"
    query = {"query": {"match_all": {}}}
    scroll_time = "1m"
    batch_size = 10 # Small size for testing

    print(f"\nAttempting initial scroll search on index '{index_name}'...")
    response = es_client.search(
        index=index_name,
        scroll=scroll_time,
        size=batch_size,
        body=query,
        _source=["content"] # Fetch minimal source
    )
    print("\nInitial scroll search COMPLETE.") # <--- Does it reach here?
    print(f"Response keys: {response.keys()}")
    print(f"Took: {response.get('took')}ms")
    print(f"Scroll ID: {response.get('_scroll_id')}")
    print(f"Hits found in first batch: {len(response.get('hits', {}).get('hits', []))}")
    print(f"Total hits estimate: {response.get('hits', {}).get('total', {}).get('value')}")

    # Clear scroll if successful
    scroll_id = response.get('_scroll_id')
    if scroll_id:
        print("\nClearing scroll context...")
        es_client.clear_scroll(scroll_id=scroll_id)
        print("Scroll context cleared.")

except Exception as e:
    print(f"\nAN ERROR OCCURRED: {type(e).__name__}: {e}")
    logging.exception("Detailed traceback:")

print("\nScript finished.")
