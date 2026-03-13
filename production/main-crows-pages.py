import requests
from bs4 import BeautifulSoup
import urllib.parse
import re
import time
import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
import json
from datetime import datetime, timedelta



def fetch_data_from_url(url):
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to fetch {url}")
        # 何らかの理由でresponseが取得できなかった場合は前回のresponseを利用する
        response = response_prev

    # 上記エラー処理のために保存しておく変数
    response_prev = response

    soup = BeautifulSoup(response.text, 'html.parser')
    script_tags = soup.find_all('script', string=re.compile(r'window\.__PRELOADED_STATE__'))

    for script in script_tags:
        match = re.search(r'window\.__PRELOADED_STATE__\s*=\s*"(.*?)";?', script.string)
        if match:
            encoded_data = match.group(1)
            decoded_data = urllib.parse.unquote(encoded_data)
            
            try:
                # デコードした文字列をJSONとしてパース（Pythonの辞書型に変換）
                json_data = json.loads(decoded_data)
                
                # 再帰的に辞書を探索し、質問のタイトルを抽出する関数
                def extract_question_data(data):
                    extracted = []
                    if isinstance(data, dict):
                        # データタイプが「QUESTION（質問）」の場合に情報を取得
                        if data.get('type') == 'QUESTION':
                            author_info = data.get('author', {})
                            extracted.append({
                                'conversationId': data.get('conversationId'),
                                'path': data.get('path'),
                                'title': data.get('title'),
                                'updatedAt': data.get('updatedAt'),
                                'username': author_info.get('username'),
                                'content': data.get('content')
                            })
                        # さらに深い階層を探索
                        for value in data.values():
                            extracted.extend(extract_question_data(value))
                    elif isinstance(data, list):
                        # リスト内の各要素を探索
                        for item in data:
                            extracted.extend(extract_question_data(item))
                    return extracted
                
                # 抽出処理の実行
                raw_data = extract_question_data(json_data)
                
                # conversationIdで重複を排除
                seen_conversation_ids = set()
                all_extracted_data = []
                for item in raw_data:
                    if item['conversationId'] not in seen_conversation_ids:
                        all_extracted_data.append(item)
                        seen_conversation_ids.add(item['conversationId'])
                
            except json.JSONDecodeError:
                print("JSONデータのパースに失敗しました。")
            break
    return(all_extracted_data)


def fetch_contentdata_from_url(url):
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to fetch {url}")
        return
    
    soup = BeautifulSoup(response.text, 'html.parser')

    # bs4で書き込みスペース名を取得(情報取得はしておくが他の所から同じ情報を取ってきているのでreturnでは返さない)
    space_name = soup.find('h2', class_='modern-banner__title').get_text(strip=True)

    # bs4でタイトルを取得(情報取得はしておくが他の所から同じ情報を取ってきているのでreturnでは返さない)
    title = soup.find('h1', class_='conversation-balloon__content__title word-wrap heading heading--h1 css-1ry1tx8 css-1pj99nl').get_text(strip=True)

    # bs4で質問者名を取得
    author = soup.find('p', class_='text-overflow text text--large css-1ry1tx8 css-okc7pe').get_text(strip=True)

    # bs4で質問内容を取得
    meta_tag = soup.find('meta', attrs={'data-react-helmet': 'true', 'name': 'description'})
    question_text = meta_tag['content']

    # bs4とdatetimeで投稿時間（日本時間はtimedeltaを利用）を取得
    meta_tag = soup.find('meta', property='article:published_time')

    if meta_tag:
        # content属性の値 (2025-11-04T00:17:42.590Z) を取得
        raw_date = meta_tag.get('content')
        
        # ISO形式の文字列をdatetimeオブジェクトに変換
        # ※末尾のZはUTC（協定世界時）を意味します
        dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
        
        # 指定の形式にフォーマット
        # %-d は0埋めなしの日にち（Windows環境では %#d）
        date_text = dt.strftime('%Y年%m月%d日%H:%M').replace(' 0', ' ')
        
        # 「04日」を「4日」にするための調整（簡易的な置換例）
        date_text = dt.strftime('%Y年%m月').replace(' 0', '') + str(dt.day) + "日" + dt.strftime(' %H:%M')

        original_time = datetime.strptime(date_text, "%Y年%m月%d日 %H:%M")
    else:
        print("該当するタグが見つかりませんでした。")

    new_time = original_time + timedelta(hours=9)

    # date_text = soup.find('p', class_='m-r-1 dell-conversation-ballon__header-date text text--normal css-1ry1tx8 css-jp8xm2').get_text(strip=True)
    # original_time = datetime.strptime(date_text, "%Y年%m月%d日 %H:%M")
    # new_time = original_time + timedelta(hours=9   #2026年2月のSprinklrのHTML仕様変更により本コードは利用できなくなったために書き換え)
    post_time = new_time.strftime('%Y-%m-%d %H:%M')

    return (space_name, author, post_time, question_text)

# 以下関数は以前利用していたが、現行では利用しないようにした
def convert_datetime_format(dt_str):
    # 文字列をPythonのdatetimeオブジェクトに変換
    dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S.%fZ")
    
    # UTCからJSTに変換 (+9時間)
    dt_jst = dt + timedelta(hours=9)
    
    # 新しい形式に変換
    return dt_jst.strftime("%Y/%m/%d %H:%M")

def convert_datetime_format_unixtime(unix_time):
    # Unixタイムスタンプをdatetimeオブジェクトに変換
    dt = datetime.fromtimestamp(unix_time)
    
    # 形式を整えて返す
    return dt.strftime("%Y/%m/%d %H:%M")

# 過去のスレッドにアクションがあった場合に新しい書き込みと認識されることを避けるために、現在時刻とスレッドのInitial書き込み時刻の差異を確認するための関数
def calculate_time_difference(datetime_str):
    # テキストデータから日時をdatetimeオブジェクトに変換
    given_datetime = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
    
    # 現在の時刻を取得
    current_datetime = datetime.now()
    
    # 差異を計算
    time_difference = current_datetime - given_datetime

    # 差異を秒数に変換
    time_difference_seconds = time_difference.total_seconds()
    
    return time_difference_seconds
    

def send_notification_email(sender_email, sender_password, recipient_emails, subject, body):
    # SMTPサーバーに接続する
    server = smtplib.SMTP("mail67.conoha.ne.jp", 587)
    server.ehlo()
    server.starttls()
    server.login(sender_email, sender_password)

    # リスト内に複数情報がある場合には複数行に分けて記載する
    main = "\n".join(body)

    # メールを送信する
    message = "Subject: {}\n\n{}".format(subject, main)
    print(f"メッセージは：{message}")

    # 実際にユーザーから見える送信元メールアドレス
    new_sender_email = "notification@storage.dellcommunity.jp"

    print(f"出力確認ポイント2：email送信開始")

    


    # メール送信部分　.encode('utf-8')は'ascii' codec can't encode characters in position 13-34: ordinal not in range(128)エラー対策
    for recipient_email in recipient_emails:
        # server.sendmail(new_sender_email, recipient_email, message.encode('utf-8'))
        # MIME形式に変換
        new_message = MIMEText(message, 'plain')
        new_message['Subject'] = subject
        new_message['From'] = new_sender_email
        new_message['To'] = recipient_email
        server.sendmail(new_sender_email, recipient_email, new_message.as_string())

    print(f"出力確認ポイント3：email送信完了")

    # SMTPサーバーを切断する
    server.quit()

def check_for_updates(url, check_interval=300):
    print("Starting to monitor websites for updates...")

    last_texts = fetch_data_from_url(url)
    
    last_texts_comp = []
    for item in last_texts:
        last_texts_comp.append(item.get('conversationId'))


    # print(last_texts_comp)
    print(last_texts)

    while True:
        time.sleep(check_interval)
        
        print("content check starts")

        current_texts = fetch_data_from_url(url)
        if current_texts is None:
            continue

        current_texts_comp = []
        for item in current_texts:
            current_texts_comp.append(item.get('conversationId'))

        if current_texts_comp != last_texts_comp:
            print("Update detected!")
            # 差分のコンテンツIDを取り出し
            current_texts_only_contid = [id for id in current_texts_comp if id not in last_texts_comp ]
            # 差分のコンテンツを全て抽出
            new_contents = [cont for cont in current_texts if cont.get('conversationId') in current_texts_only_contid]

            # print(new_contents)

            body = []
            title = ""
            for content in new_contents:
                title = content['title']
                url = 'https://www.dell.com/community/ja/conversations/'+content['path']
                author = content['username']
                # updatedAtの値が入ってこないケースがあるために、その場合には代わりに0を代入する
                unix_time = (content['updatedAt'] or 0) / 1000
                post_time = convert_datetime_format_unixtime(unix_time)
                question_text = content['content']
                
                body.append(f"タイトル： {title}\n\nURL: {url}\n\n質問者: {author}\n\n投稿時間: {post_time}\n\n質問内容: {question_text}")

            # print(body)

            # 環境変数からメールアドレスとパスワードを取得する
            load_dotenv()  # .envファイルから環境変数を読み込む
            sender_email = os.environ.get("SENDER_EMAIL")
            sender_password = os.environ.get("SENDER_PASSWORD")

            # メールを送信する
            try:
                recipient_emails = os.environ.get("RECIPIENT_EMAILS")
                recipient_emails = list(recipient_emails.split(","))
                # 変更確認対象URLページが「解決済み」マークの付与でも変更されてしまうので、新規書き込み時とのタイトル場合分け

                # if body == []:   #このブロックは旧バージョン。解決済みマークがついた時に空メールを送る仕様。
                #     email_title = "Dellコミュニティ_誰かが「解決済み」マークを付けたようです（確認の必要はありません）"
                # else:
                #     email_title = "Dellコミュニティに新規コンテンツが投稿されました"

                content_no = len(new_contents)

                email_title = f"{content_no}:Dellコミュニティに新規コンテンツが投稿されました-{title}"

                if body != []:         
                    send_notification_email(
                    sender_email, sender_password, recipient_emails, email_title, body
                    )
            except Exception as e:
                print(f"メール送信に失敗しました：{e}")

            print(f"出力確認ポイント4：email送信処理完了（注：空メールは送信しません）")

            # 最新のコンテンツを今後の比較対象とする
            last_texts = current_texts



def main():
    url_to_check = "https://www.dell.com/community/ja/categories/%E3%82%BD%E3%83%AA%E3%83%A5%E3%83%BC%E3%82%B7%E3%83%A7%E3%83%B3%EF%BC%86%E3%82%B5%E3%83%BC%E3%83%93%E3%82%B9"

    try:
        check_for_updates(url_to_check)
    except Exception as e:
        print(f"アップデート確認処理に失敗しました：{e}")


if __name__ == "__main__":
    main()




