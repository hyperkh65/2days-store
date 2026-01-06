from flask import Flask, request, jsonify, render_template
from google.oauth2 import service_account
from googleapiclient.discovery import build
import resend
import os
import json

app = Flask(__name__)

# Resend API 키 설정
resend.api_key = os.environ.get('RESEND_API_KEY')


# Google Drive 설정
def get_drive_service():
    creds_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT')
    creds_dict = json.loads(creds_json)

    credentials = service_account.Credentials.from_service_account_info(
        creds_dict,
        scopes=['https://www.googleapis.com/auth/drive']
    )

    return build('drive', 'v3', credentials=credentials)


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/api/send-product', methods=['POST'])
def send_product():
    try:
        data = request.get_json()
        email = data.get('email')
        product_code = data.get('productCode')

        # 입력 검증
        if not email or not product_code:
            return jsonify({'error': '이메일과 상품번호를 입력해주세요'}), 400

        # Google Drive에서 파일 검색
        drive_service = get_drive_service()

        results = drive_service.files().list(
            q=f"name contains '{product_code}' and trashed=false",
            fields='files(id, name)',
            pageSize=1
        ).execute()

        files = results.get('files', [])

        if not files:
            return jsonify({'error': '상품번호를 찾을 수 없습니다'}), 404

        file = files[0]
        file_id = file['id']
        file_name = file['name']

        # 파일 공유 권한 설정
        drive_service.permissions().create(
            fileId=file_id,
            body={'role': 'reader', 'type': 'anyone'}
        ).execute()

        # 다운로드 링크 생성
        download_link = f"https://drive.google.com/uc?export=download&id={file_id}"
        view_link = f"https://drive.google.com/file/d/{file_id}/view"

        # Resend로 이메일 발송
        params = {
            "from": "2Days Store <noreply@file.2days.kr>",
            "to": [email],   # 사용자가 입력한 이메일
            "subject": f"[2Days] {file_name} 다운로드 준비 완료! 🎉",
            "html": f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: -apple-system, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; }}
                    .header {{ background: linear-gradient(135deg, #7c3aed 0%, #3b82f6 100%); 
                              padding: 30px; text-align: center; border-radius: 12px 12px 0 0; }}
                    .header h1 {{ color: white; margin: 0; }}
                    .content {{ background: #f9fafb; padding: 30px; }}
                    .product-card {{ background: white; border-radius: 12px; padding: 20px; 
                                    margin: 20px 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
                    .button {{ display: inline-block; padding: 14px 32px; 
                              background: linear-gradient(135deg, #7c3aed 0%, #3b82f6 100%);
                              color: white; text-decoration: none; border-radius: 8px; 
                              font-weight: 600; margin: 10px 5px; }}
                    .footer {{ text-align: center; padding: 20px; color: #6b7280; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🎁 상품 다운로드 준비 완료!</h1>
                    </div>
                    <div class="content">
                        <div class="product-card">
                            <h2 style="color: #7c3aed;">📦 {file_name}</h2>
                            <p style="color: #6b7280;">상품번호: <strong>{product_code}</strong></p>
                            <p>구매하신 디지털 상품이 준비되었습니다!</p>
                            <div style="text-align: center; margin: 30px 0;">
                                <a href="{download_link}" class="button">⬇️ 지금 다운로드</a>
                                <a href="{view_link}" class="button">👀 미리보기</a>
                            </div>
                        </div>
                        <div style="background: #fef3c7; border-left: 4px solid #f59e0b; 
                                    padding: 15px; border-radius: 8px;">
                            <p><strong>💡 안내사항</strong></p>
                            <ul>
                                <li>다운로드 링크는 30일간 유효합니다</li>
                                <li>문제 발생 시 상품번호와 함께 문의해주세요</li>
                            </ul>
                        </div>
                    </div>
                    <div class="footer">
                        <p>© 2026 2Days. All rights reserved.</p>
                        <p><a href="https://2days.kr" style="color: #7c3aed;">블로그 방문하기</a></p>
                    </div>
                </div>
            </body>
            </html>
            """
        }

        email_response = resend.Emails.send(params)

        return jsonify({
            'success': True,
            'message': '이메일이 발송되었습니다',
            'emailId': email_response['id']
        }), 200

    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'error': '서버 오류가 발생했습니다'}), 500


if __name__ == '__main__':
    app.run(debug=True)