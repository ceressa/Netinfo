import random
import string
import hashlib


class MemorablePasswordGenerator:
    def __init__(self):
        # Türkçe kelimeler (Network/IT temalı)
        self.turkish_words = [
            "Ağ", "Bağlantı", "Güvenlik", "Trafik", "Anahtar", "Köprü",
            "Merkez", "Portal", "Kanal", "Sinyal", "Veri", "Sistem"
        ]

        # İngilizce IT kelimeleri
        self.english_words = [
            "Network", "Secure", "Admin", "Portal", "Gateway", "Bridge",
            "Server", "Router", "Switch", "Traffic", "Monitor", "Guard"
        ]

        # FedEx temalı kelimeler
        self.fedex_words = [
            "Express", "Delivery", "Package", "Fast", "Global", "Connect",
            "Service", "Priority", "Urgent", "Ship", "Track", "Ground"
        ]

        # Anlamlı sayılar
        self.meaningful_numbers = {
            "2024": "Bu yıl",
            "365": "Yıl günü",
            "24": "Saat sayısı",
            "7": "Hafta günü",
            "52": "Yıl haftası",
            "12": "Ay sayısı",
            "60": "Dakika/saniye",
            "100": "Yüzde"
        }

        # Görsel karakterler
        self.visual_chars = {
            "@": "At işareti",
            "#": "Hashtag",
            "$": "Dolar",
            "!": "Ünlem",
            "&": "Ve işareti",
            "*": "Yıldız",
            "+": "Artı",
            "=": "Eşittir"
        }

    def generate_story_password(self):
        """Hikaye tabanlı şifre üret"""
        stories = [
            {
                "story": "FedEx Ağında 2024 yılında 365 gün güvenlik!",
                "password": "FedEx@Ag2024#365Gun!",
                "memory": "FedEx + Ağ + 2024 + 365 Gün + ünlem"
            },
            {
                "story": "Network Monitoring için 24 saat 7 gün aktif sistem",
                "password": "Network24$7Gun&Aktif!",
                "memory": "Network + 24 saat + 7 gün + aktif + ünlem"
            },
            {
                "story": "Güvenli Portal'a sadece Admin'ler 2024'te erişir",
                "password": "Guvenli#Portal2024@Admin!",
                "memory": "Güvenli + Portal + 2024 + Admin + ünlem"
            }
        ]
        return random.choice(stories)

    def generate_pattern_password(self):
        """Kalıp tabanlı şifre"""
        patterns = [
            {
                "pattern": "[İngilizce Kelime][Sayı][Türkçe][Sembol][Yıl]",
                "example": "Secure12Ag!2024",
                "memory": "Secure + 12 + Ağ + ünlem + 2024"
            },
            {
                "pattern": "[FedEx Kelime][Sembol][Sayı][IT Kelime][Yıl]",
                "example": "Express$60Network2024",
                "memory": "Express + dolar + 60 + Network + 2024"
            }
        ]

        pattern = random.choice(patterns)

        # Rastgele kelimeler seç
        eng_word = random.choice(self.english_words)
        tr_word = random.choice(self.turkish_words)
        fedex_word = random.choice(self.fedex_words)
        number = random.choice(list(self.meaningful_numbers.keys()))
        symbol = random.choice(list(self.visual_chars.keys()))

        passwords = [
            f"{eng_word}{number}{tr_word}{symbol}2024",
            f"{fedex_word}{symbol}{number}{eng_word}2024",
            f"Tr{tr_word}{number}{symbol}{eng_word}!"
        ]

        return {
            "pattern": pattern["pattern"],
            "password": random.choice(passwords),
            "memory": f"{eng_word} + {number} + {tr_word} + {symbol} + 2024"
        }

    def generate_personal_password(self):
        """Kişisel bilgi tabanlı şifre"""
        print("\n🤔 KİŞİSEL BİLGİ BAZLI ŞİFRE")
        print("=" * 40)

        questions = [
            ("Doğum ayın (rakam):", "birth_month"),
            ("En sevdiğin renk:", "color"),
            ("Kaç yıldır FedEx'tesin:", "fedex_years"),
            ("En sevdiğin şehir:", "city")
        ]

        answers = {}
        for question, key in questions:
            answer = input(question + " ").strip()
            answers[key] = answer

        # Şifre kombinasyonları oluştur
        combinations = [
            f"FedEx{answers['fedex_years']}Yil@{answers['color']}2024!",
            f"{answers['city']}{answers['birth_month']}#{answers['color']}Fedex!",
            f"Ag{answers['color']}@{answers['fedex_years']}Yil2024!"
        ]

        return {
            "passwords": combinations,
            "memory_tips": [
                f"FedEx + {answers['fedex_years']} yıl + @ + {answers['color']} + 2024 + ünlem",
                f"{answers['city']} + {answers['birth_month']} + # + {answers['color']} + FedEx + ünlem",
                f"Ağ + {answers['color']} + @ + {answers['fedex_years']} yıl + 2024 + ünlem"
            ]
        }

    def generate_acronym_password(self):
        """Kısaltma tabanlı şifre"""
        sentences = [
            {
                "sentence": "FedEx Türkiye Ağında Güvenlik Çok Önemlidir 2024",
                "acronym": "FeTAGCO2024",
                "with_symbols": "FeTAGCO@2024!",
                "memory": "FedEx Türkiye Ağında Güvenlik Çok Önemlidir + @ + 2024 + ünlem"
            },
            {
                "sentence": "Network Monitoring Her Gün 24 Saat Aktif",
                "acronym": "NMHG24SA",
                "with_symbols": "NMHG24$A!",
                "memory": "Network Monitoring Her Gün 24 Saat Aktif + dolar + ünlem"
            },
            {
                "sentence": "Admin Paneli Sadece Yetkili Kişiler Kullanır",
                "acronym": "APSYKK",
                "with_symbols": "APSYKK@2024!",
                "memory": "Admin Paneli Sadece Yetkili Kişiler Kullanır + @ + 2024 + ünlem"
            }
        ]

        return random.choice(sentences)

    def test_password_strength(self, password):
        """Şifre gücünü test et"""
        score = 0
        feedback = []

        if len(password) >= 12:
            score += 2
        elif len(password) >= 8:
            score += 1
        else:
            feedback.append("❌ En az 8 karakter olmalı")

        if any(c.isupper() for c in password):
            score += 1
        else:
            feedback.append("❌ Büyük harf eksik")

        if any(c.islower() for c in password):
            score += 1
        else:
            feedback.append("❌ Küçük harf eksik")

        if any(c.isdigit() for c in password):
            score += 1
        else:
            feedback.append("❌ Sayı eksik")

        if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            score += 1
        else:
            feedback.append("❌ Özel karakter eksik")

        if score >= 5:
            strength = "🟢 ÇOK GÜÇLÜ"
        elif score >= 4:
            strength = "🟡 GÜÇLÜ"
        elif score >= 3:
            strength = "🟠 ORTA"
        else:
            strength = "🔴 ZAYIF"

        return strength, feedback

    def run(self):
        """Ana menü"""
        while True:
            print("\n🧠 AKILDA KALAN GÜVENLİ ŞİFRE ÜRETİCİSİ")
            print("=" * 50)
            print("1. 📖 Hikaye Tabanlı Şifre")
            print("2. 🎯 Kalıp Tabanlı Şifre")
            print("3. 👤 Kişisel Bilgi Tabanlı Şifre")
            print("4. 🔤 Kısaltma Tabanlı Şifre")
            print("5. 🧪 Mevcut Şifremi Test Et")
            print("6. 🚪 Çıkış")

            choice = input("\nSeçim (1-6): ").strip()

            if choice == "1":
                result = self.generate_story_password()
                print(f"\n📖 HİKAYE: {result['story']}")
                print(f"🔐 ŞİFRE: {result['password']}")
                print(f"🧠 HATIRLA: {result['memory']}")

                strength, feedback = self.test_password_strength(result['password'])
                print(f"💪 GÜÇ: {strength}")

            elif choice == "2":
                result = self.generate_pattern_password()
                print(f"\n🎯 KALIP: {result['pattern']}")
                print(f"🔐 ŞİFRE: {result['password']}")
                print(f"🧠 HATIRLA: {result['memory']}")

                strength, feedback = self.test_password_strength(result['password'])
                print(f"💪 GÜÇ: {strength}")

            elif choice == "3":
                result = self.generate_personal_password()
                print(f"\n🔐 ÖNERİLEN ŞİFRELER:")
                for i, (pwd, memory) in enumerate(zip(result['passwords'], result['memory_tips']), 1):
                    print(f"{i}. {pwd}")
                    print(f"   🧠 {memory}")
                    strength, _ = self.test_password_strength(pwd)
                    print(f"   💪 {strength}\n")

            elif choice == "4":
                result = self.generate_acronym_password()
                print(f"\n📝 CÜMLE: {result['sentence']}")
                print(f"🔤 KISALTMA: {result['acronym']}")
                print(f"🔐 ŞİFRE: {result['with_symbols']}")
                print(f"🧠 HATIRLA: {result['memory']}")

                strength, feedback = self.test_password_strength(result['with_symbols'])
                print(f"💪 GÜÇ: {strength}")

            elif choice == "5":
                test_pwd = input("Test edilecek şifreyi gir: ")
                strength, feedback = self.test_password_strength(test_pwd)
                print(f"\n💪 GÜÇ: {strength}")
                if feedback:
                    print("📋 ÖNERİLER:")
                    for tip in feedback:
                        print(f"   {tip}")

            elif choice == "6":
                print("👋 Güvenli şifreler dilerim!")
                break

            else:
                print("❌ Geçersiz seçim!")

            input("\nDevam etmek için Enter'a bas...")


if __name__ == "__main__":
    generator = MemorablePasswordGenerator()
    generator.run()
