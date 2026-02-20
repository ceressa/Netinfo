from flask import Flask, request, jsonify
import requests
import pandas as pd

app = Flask(__name__)

@app.route('/Netinfo/api/get_report', methods=['GET'])
def get_report():
    deviceid = request.args.get('deviceid')
    if not deviceid:
        return jsonify({"error": "Device ID gerekli"}), 400

    api_url = f"https://statseeker.emea.fedex.com/api/v2.1/cdt_port/?fields=deviceid,name,ifTitle,ifSpeed,ifDescr,ifAdminStatus,if90day&deviceid={deviceid}"
    username = "tr-api"
    password = "F3xpres!"

    response = requests.get(api_url, auth=(username, password), verify=False)
    if response.status_code != 200:
        return jsonify({"error": "Statseeker API isteği başarısız"}), 500

    try:
        data = response.json()
        data_objects = data["data"]["objects"][0]["data"]
        df = pd.DataFrame(data_objects)

        df["ifSpeed"] = df["ifSpeed"].fillna(0).astype(int) // 1000000
        df["if90day"] = df["if90day"].apply(lambda x: "Aktif" if x == 1 else "Aktif değil")

        result = df.rename(columns={
            "deviceid": "Device ID",
            "name": "Interface",
            "ifTitle": "Tanım",
            "ifSpeed": "Hız (Mbps)",
            "ifDescr": "Açıklama",
            "ifAdminStatus": "Durum",
            "if90day": "90 Gün"
        }).to_dict(orient="records")

        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Veri işleme hatası: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)  # Debug modunu etkinleştir

