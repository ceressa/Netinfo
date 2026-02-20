import qrcode

# QR kodu için URL
url = "https://tr.eu.fedex.com/Netinfo/index5.html?uuid=4wsm5aq2-fdx-8146"

# QR kodu oluştur
qr = qrcode.QRCode(
    version=1,  # QR kodun karmaşıklık seviyesi (1 en basit)
    error_correction=qrcode.constants.ERROR_CORRECT_L,  # Hata düzeltme seviyesi
    box_size=10,  # Her kutunun piksel boyutu
    border=4,  # Çerçeve genişliği (kare sayısı)
)

qr.add_data(url)  # URL'yi QR koda ekle
qr.make(fit=True)

# QR kodu bir görüntü olarak kaydet
img = qr.make_image(fill_color="black", back_color="white")

# Dosya olarak kaydet
img.save("qrcode.png")

print("QR kodu başarıyla oluşturuldu ve 'qrcode.png' dosyasına kaydedildi.")
