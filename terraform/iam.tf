# This is the IAM role the Lambda function will run as - equivalent to the
# execution role that Lambda auto-created for you when you built the first
# function through the console. Here, we define it explicitly.

resource "aws_iam_role" "triage_lambda_role" {
  name = "triage-lambda-tf-role"

  # This "assume role policy" says: "AWS Lambda is allowed to use this role."
  # It's boilerplate required for any Lambda execution role.
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# Basic permissions every Lambda function needs: writing logs to CloudWatch.
# Without this, the function would run but you'd have no logs to debug with.
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.triage_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Bedrock access, same as we attached manually to the first Lambda function's
# auto-created role.
resource "aws_iam_role_policy_attachment" "lambda_bedrock_access" {
  role       = aws_iam_role.triage_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonBedrockFullAccess"
}
