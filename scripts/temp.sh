# list resourceId + path for /v1/*
aws apigateway get-resources --rest-api-id "$API_ID" \
| jq -r '.items[] | select(.path | startswith("/v1")) | "\(.id) \(.path)"' \
| while read RID PATH; do
  # discover methods for the resource
  METHODS=$(aws apigateway get-resource --rest-api-id "$API_ID" --resource-id "$RID" \
            | jq -r '(.resourceMethods // {} ) | keys[]?' )
  for M in $METHODS; do
    AWS_METHOD=$(aws apigateway get-method --rest-api-id "$API_ID" --resource-id "$RID" --http-method "$M")
    AUTH_TYPE=$(echo "$AWS_METHOD" | jq -r '.authorizationType')
    AUTHZ_ID=$(echo "$AWS_METHOD" | jq -r '.authorizerId // empty')
    printf "%-6s %-35s  auth=%s  authorizerId=%s\n" "$M" "$PATH" "$AUTH_TYPE" "${AUTHZ_ID:-none}"
    if [ "$AUTH_TYPE" != "COGNITO_USER_POOLS" ]; then
      echo "❌ $M $PATH is not protected by Cognito"
      exit 2
    fi
  done
done
echo "✅ All /v1 methods protected by Cognito"
