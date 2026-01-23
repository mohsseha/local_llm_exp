import mailparser
import base64
import sys

print(f"--- Running Interactive Python Tests ---")

try:
    # Parse the test EML file
    parser = mailparser.parse_from_file('docs2md/interactive_test.eml')
    
    # --- Test 1: Inspect the 'from_' address structure ---
    print("\n[Test 1: Address Structure]")
    from_address_list = parser.from_
    print(f"  - Raw 'from_': {from_address_list}")
    print(f"  - Type of 'from_': {type(from_address_list)}")
    
    if from_address_list:
        first_address_tuple = from_address_list[0]
        print(f"  - First address tuple: {first_address_tuple}")
        name, addr = first_address_tuple
        print(f"  - Extracted Name: '{name}', Extracted Address: '{addr}'")
    
    # --- Test 2: Inspect the attachment payload ---
    print("\n[Test 2: Attachment Payload]")
    if parser.attachments:
        attachment = parser.attachments[0]
        payload = attachment['payload']
        print(f"  - Raw Payload: '{payload}'")
        print(f"  - Type of Payload: {type(payload)}")
        
        # --- Test 3: Decode the payload ---
        print("\n[Test 3: Decoding Payload]")
        if isinstance(payload, str):
            # If it's a string, it needs to be encoded to bytes before b64decode
            decoded_payload = base64.b64decode(payload.encode('ascii'))
            print(f"  - Successfully decoded from STRING.")
        elif isinstance(payload, bytes):
            decoded_payload = base64.b64decode(payload)
            print(f"  - Successfully decoded from BYTES.")
        else:
            decoded_payload = b"Unknown payload type"

        print(f"  - Decoded Content: {decoded_payload}")
        print(f"  - Decoded as UTF-8: '{decoded_payload.decode('utf-8')}'")

    print("\n--- Tests Completed Successfully ---")

except Exception as e:
    print(f"\n--- ERROR DURING TESTING ---", file=sys.stderr)
    print(f"  - Exception: {type(e).__name__}", file=sys.stderr)
    print(f"  - Details: {e}", file=sys.stderr)
