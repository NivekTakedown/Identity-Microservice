BASE_URL="http://localhost:8000"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "Testing Identity Microservice Endpoints"

# 1. Get JWT Token
echo -e "${YELLOW}Getting JWT Token...${NC}"
TOKEN_RESPONSE=$(curl -s -X POST "${BASE_URL}/auth/token" \
  -H "Content-Type: application/json" \
  -d '{"grant_type":"password","username":"mrios","password":"admin_pass"}')

JWT_TOKEN=$(echo $TOKEN_RESPONSE | jq -r '.access_token')

if [ "$JWT_TOKEN" = "null" ]; then
  echo -e "${RED}Failed to get token${NC}"
  exit 1
fi

echo -e "${GREEN}Token obtained successfully${NC}"

# 2. Test Authentication
echo -e "${YELLOW}Testing Authentication...${NC}"
curl -s -X GET "${BASE_URL}/auth/me" \
  -H "Authorization: Bearer $JWT_TOKEN" | jq '.sub'

# 3. Test SCIM Users
echo -e "${YELLOW}Testing SCIM Users...${NC}"
curl -s -X GET "${BASE_URL}/scim/v2/Users" | jq '.totalResults'

# 4. Test SCIM Groups
echo -e "${YELLOW}Testing SCIM Groups...${NC}"
curl -s -X GET "${BASE_URL}/scim/v2/Groups" | jq '.totalResults'

# 5. Test Authorization
echo -e "${YELLOW}Testing Authorization...${NC}"
curl -s -X POST "${BASE_URL}/authz/evaluate" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{
    "subject": {"dept": "IT", "groups": ["ADMINS"], "riskScore": 15},
    "resource": {"type": "user_data", "env": "dev"},
    "context": {"geo": "CL", "deviceTrusted": true}
  }' | jq '.decision'

echo -e "${GREEN}All tests completed${NC}"