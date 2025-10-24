from pathlib import Path
import os

# 프로젝트 루트 기준 docs/openapi.yml 경로
SPEC_PATH = Path(__file__).resolve().parents[2] / "docs" / "openapi.yml"
SPEC_TEXT = SPEC_PATH.read_text(encoding="utf-8")

SWAGGER_HTML = """<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>API Docs</title>
    <link rel="stylesheet"
      href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
  </head>
  <body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
      window.onload = () => {
        SwaggerUIBundle({
          url: "openapi.yml",   // 경로 기준에 맞게 상대 경로로 요청 (/docs → /openapi.yml, /api/docs → /api/openapi.yml)
          dom_id: "#swagger-ui",
          docExpansion: "none",
          deepLinking: true,
        });
      };
    </script>
  </body>
</html>"""


def serve_swagger_ui(event, context):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "text/html; charset=utf-8"},
        "body": SWAGGER_HTML,
    }


def serve_openapi(event, context):
    # 환경변수에서 API Gateway ID 가져오기
    api_gateway_id = os.environ.get("API_GATEWAY_ID")

    # OpenAPI 스펙에서 환경변수 치환
    spec_text = SPEC_TEXT.replace("${env:API_GATEWAY_ID}", api_gateway_id)

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/yml; charset=utf-8"},
        "body": spec_text,
    }
