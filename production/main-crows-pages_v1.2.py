import requests
from bs4 import BeautifulSoup
import time
import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
import json
from datetime import datetime, timedelta
import urllib.parse


def fetch_data_from_url(url):
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to fetch {url}")
        return
    
    soup = BeautifulSoup(response.text, 'html.parser')

    # すべての<a>タグを検索
    links = soup.find_all('a', title=True, href=True)

    # 各リンクのtitleとhrefをディクショナリに保存
    title_url_dict = {link['title']: link['href'] for link in links}

    return(title_url_dict)

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
    date_text = soup.find('p', class_='m-r-1 dell-conversation-ballon__header-date text text--normal css-1ry1tx8 css-jp8xm2').get_text(strip=True)
    original_time = datetime.strptime(date_text, "%Y年%m月%d日 %H:%M")
    new_time = original_time + timedelta(hours=9)
    post_time = new_time.strftime('%Y-%m-%d %H:%M')

    return (space_name, author, post_time, question_text)

# 以下関数は以前利用していたが、現行では利用しないようにした
def convert_datetime_format(dt_str):
    # 文字列をPythonのdatetimeオブジェクトに変換
    dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S.%fZ")
    
    # UTCからJSTに変換 (+9時間)
    dt_jst = dt + timedelta(hours=9)
    
    # 新しい形式に変換
    return dt_jst.strftime("%Y/%-m/%-d %-H:%M")

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

    print(last_texts)

    while True:
        time.sleep(check_interval)

        current_texts = fetch_data_from_url(url)
        if current_texts is None:
            continue

        if current_texts != last_texts:
            print(f"Update detected on {url}!")
            print(f"Current_texts is {current_texts}")
            print("\n")
            print(f"Last_texts is {last_texts}")
            added = {k: v for k, v in current_texts.items() if k not in last_texts}
            print("新規コンテンツ情報：", added)

            body = []
            title = ""
            for i, v in added.items():
                # urlの中に日本語のキャラクターがあると上手く動作しないのでUTF-8でエンコード
                url_utf8 = urllib.parse.quote(v, encoding="utf-8")
                v2 = f"https://www.dell.com{url_utf8}"
                # UTF-8でダブルバイトが入るとリンクが動作しなくなったのでURLエンコード
                v3 = urllib.parse.quote(v2, safe='/:?=&')

                # どうやってもリンク出来るURLがメールに入ってこないので、別のテキストを準備することにした
                splittexts = url_utf8.split('/')
                threadid = splittexts[-1]

                # 固定のURLプレフィックス
                base_url = "https://www.dell.com/community/en/conversations/x//"

                v4 = base_url + threadid.astype(str) 


                title = i
                print(f"確認URLは： {v3}")
                try:
                    space_name, author, post_time, question_text = fetch_contentdata_from_url(v2)
                    # 新規書き込みか、過去の書き込みへのアクションなのかを確認するために現在時刻との時間差異を確認
                    post_time_difference = calculate_time_difference(post_time)
                    # もしも時間差異が10分以内であればメール送信のためのbodyを作成
                    if post_time_difference < 600:
                        body.append(f"タイトル：{i}\n\nスペース：{space_name}\n\nURL: {v4}\n\n質問者: {author}\n\n投稿時間: {post_time}\n\n質問内容:\n{question_text}\n\n\n")
                except Exception as e:
                    print(f"コンテンツ詳細情報取得に失敗しました：{e}")  

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

                content_no = len(added)

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




