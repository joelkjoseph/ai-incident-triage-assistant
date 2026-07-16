# The Lambda function itself. This reuses the same container image already
# sitting in ECR (built and pushed manually earlier) - Terraform doesn't
# need to know how that image was built, just where to find it.

resource "aws_lambda_function" "triage_lambda_tf" {
  function_name = "triage-lambda-tf"

  # Points at the same image you already pushed with the "lambda" tag.
  package_type = "Image"
  image_uri    = "691768189622.dkr.ecr.us-east-1.amazonaws.com/triage-app:lambda"

  role = aws_iam_role.triage_lambda_role.arn

  # Same values we set manually via the console earlier, now defined as code.
  memory_size = 2048
  timeout     = 30

  environment {
    variables = {
      HOME = "/tmp"
    }
  }
}

# Exposes the function as a public HTTPS URL, same as the console's
# "Function URL" feature we used before.
resource "aws_lambda_function_url" "triage_lambda_tf_url" {
  function_name      = aws_lambda_function.triage_lambda_tf.function_name
  authorization_type = "NONE"
}

# Setting authorization_type = "NONE" above only configures the URL itself -
# it does NOT automatically grant public invoke permission. When you create
# a Function URL through the AWS Console, it adds this permission silently
# on your behalf. In Terraform, we have to add it explicitly: this statement
# grants "anyone" (principal "*") permission to invoke the function via its
# Function URL specifically (not via other means like the console Test button).
resource "aws_lambda_permission" "public_function_url_access" {
  statement_id           = "AllowPublicFunctionUrlInvoke"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.triage_lambda_tf.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

# IMPORTANT - manual step required outside Terraform:
#
# Since October 2025, AWS requires a SECOND permission alongside the one
# above: lambda:InvokeFunction, conditioned on being invoked via a Function
# URL specifically. This uses a different mechanism (the --invoked-via-
# function-url CLI flag, corresponding to a Bool condition on
# lambda:InvokedViaFunctionUrl) than the function_url_auth_type argument
# used above, and is not currently exposed as a clean argument on this
# provider version's aws_lambda_permission resource.
#
# This was added manually via the AWS CLI:
#
#   aws lambda add-permission \
#     --function-name triage-lambda-tf \
#     --statement-id FunctionURLAllowInvokeAction \
#     --action lambda:InvokeFunction \
#     --principal "*" \
#     --invoked-via-function-url \
#     --region us-east-1
#
# This is a known gap between this Terraform config and actual deployed
# state - a real-world example of infrastructure code not being 100%
# complete on its own, and needing a documented manual step alongside it.

# Prints the live URL to the terminal after Terraform finishes, so you don't
# have to go find it in the console.
output "function_url" {
  value = aws_lambda_function_url.triage_lambda_tf_url.function_url
}
