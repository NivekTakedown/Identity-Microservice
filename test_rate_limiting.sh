BASE_URL="http://localhost:8000"

echo "Testing Rate Limiting (100 requests to /authz/evaluate)"

# Get token first
JWT_TOKEN=$(curl -s -X POST "${BASE_URL}/auth/token" \
  -H "Content-Type: application/json" \
  -d '{"grant_type":"password","username":"mrios","password":"admin_pass"}' \
  | jq -r '.access_token')

# Send 105 requests to trigger rate limiting
for i in {1..105}; do
  echo "Request $i"
  RESPONSE=$(curl -s -X POST "${BASE_URL}/authz/evaluate" \
    -H "Authorization: Bearer $JWT_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"subject":{"dept":"HR"},"resource":{"type":"test"},"context":{"geo":"CL"}}')
  
  echo $RESPONSE | jq '.detail // .decision'
  sleep 0.5
done