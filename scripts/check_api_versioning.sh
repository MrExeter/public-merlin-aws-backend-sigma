## Get the RestApi ID from your stack output
#API_ID=$(aws cloudformation describe-stacks \
#  --stack-name UsageApiStack \
#  --query "Stacks[0].Outputs[?OutputKey=='UsageApiId'].OutputValue" \
#  --output text)
#
## Show all paths + methods
#aws apigateway get-resources --rest-api-id "$API_ID" --embed methods \
#  | jq -r '.items[] | "\(.path)  \((.resourceMethods|keys)//[])"'
#
## Fail if any non-/v1 paths (excluding "/")
#aws apigateway get-resources --rest-api-id "$API_ID" --embed methods \
#  | jq -r '.items[] | select(.path != "/" and (.path | startswith("/v1") | not)) | .path' | tee /dev/stderr \
#  | { read line && { echo "❌ Non-versioned route found: $line"; exit 1; } || echo "✅ All routes under /v1"; }


API_ID=$(aws cloudformation describe-stacks \
  --stack-name UsageApiStack \
  --query "Stacks[0].Outputs[?OutputKey=='UsageApiId'].OutputValue" \
  --output text)

aws apigateway get-resources --rest-api-id "$API_ID" --embed methods \
| jq -r '.items[] | "\(.path)\t\(((.resourceMethods // {}) | keys | join(",")))"'

