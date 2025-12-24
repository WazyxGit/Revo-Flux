import sys
import json
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QSplitter, QListWidget,
                             QLineEdit, QPushButton, QMessageBox, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QMenu, QInputDialog)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, Qt, QTimer, QSettings
from PyQt6.QtGui import QDesktopServices, QFont, QClipboard, QPixmap, QIcon
from PyQt6.QtWebEngineCore import QWebEngineUrlRequestInterceptor
import feedparser

# Fonction pour gérer les chemins des ressources (dev + exe compilé)
def resource_path(relative_path):
    """ Retourne le chemin correct pour les fichiers inclus dans l'exe PyInstaller """
    if getattr(sys, 'frozen', False):
        # En mode .exe, les fichiers sont extraits dans un dossier temporaire
        base_path = sys._MEIPASS
    else:
        # En mode développement
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class RSSReader(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("REVOFLUX Alpha v1.0 - Lecteur RSS by Wazyx")

        # Icône de la fenêtre (barre des tâches + titre)
        self.setWindowIcon(QIcon(resource_path("icon.ico")))

        self.showMaximized()

        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #292d3e; color: #bec7cc; }
            QListWidget { background-color: #292d3e; border: 4px solid #31364a; color: #bec7cc; selection-background-color: #242839; }
            QLineEdit { background-color: #292d3e; border: 4px solid #242839; color: #bec7cc; padding: 10px; }
            QPushButton { background-color: #242839; border: 4px solid #292d3e; color: #bec7cc; padding: 10px; font-size: 16px; border-radius: 8px; }
            QPushButton:hover { background-color: #212432; }
            QSplitter::handle { background-color: #242839; width: 6px; }
            QLabel#titleLabel { font-size: 24px; font-weight: bold; color: #bec7cc; padding: 10px; }
        """)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # === Panneau gauche : Flux ===
        left_widget = QWidget()
        left_layout = QVBoxLayout()

        # --- En-tête avec logo et titre ---
        header_layout = QHBoxLayout()
        header_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        logo_label = QLabel()
        logo_pixmap = QPixmap(resource_path("logo.png"))
        if not logo_pixmap.isNull():
            logo_pixmap = logo_pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(logo_pixmap)
        else:
            # Fallback si logo.png manquant
            logo_label.setText("📡")
            logo_label.setStyleSheet("font-size: 36px;")
        header_layout.addWidget(logo_label)

        title_label = QLabel("REVOFLUX")
        title_label.setObjectName("titleLabel")
        title_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        left_layout.addLayout(header_layout)

        # Champ d'ajout et bouton
        self.feed_input = QLineEdit()
        self.feed_input.setPlaceholderText("Entrez l'URL du flux RSS/Atom")
        add_button = QPushButton("Ajouter un Flux")
        add_button.clicked.connect(self.add_feed)
        left_layout.addWidget(self.feed_input)
        left_layout.addWidget(add_button)

        # Liste des flux
        self.feed_list = QListWidget()
        self.feed_list.itemClicked.connect(self.load_articles)
        self.feed_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.feed_list.customContextMenuRequested.connect(self.show_feed_context_menu)
        left_layout.addWidget(self.feed_list)

        left_widget.setLayout(left_layout)
        splitter.addWidget(left_widget)

        # === Panneau central : Articles ===
        self.article_list = QListWidget()
        self.article_list.itemClicked.connect(self.display_article)
        splitter.addWidget(self.article_list)

        # === Panneau droit : Contenu ===
        self.article_view = QWebEngineView()
        self.article_view.page().setBackgroundColor(Qt.GlobalColor.transparent)
        splitter.addWidget(self.article_view)

        splitter.setSizes([400, 400, 1000])
        self.setCentralWidget(splitter)

        # Menu contextuel général
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_global_context_menu)

        self.feed_file = "feeds.json"
        self.read_file = "read_articles.json"
        self.settings = QSettings("Wazyx", "REVOFLUX")

        self.feeds = {}
        self.read_articles = set()

        self.load_saved_feeds()
        self.load_read_articles()

        # Timer actualisation auto
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_all_feeds)
        interval_sec = self.settings.value("refresh_interval", 60, int)
        interval_sec = max(30, min(120, interval_sec))
        self.refresh_timer.start(interval_sec * 1000)

    def load_saved_feeds(self):
        if os.path.exists(self.feed_file):
            try:
                with open(self.feed_file, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                for saved_title, url in saved.items():
                    feed = feedparser.parse(url)
                    title = feed.feed.title if hasattr(feed.feed, 'title') and feed.feed.title else saved_title
                    self.feeds[title] = {'url': url, 'entries': feed.entries}
                    self.update_feed_item(title)
            except Exception:
                pass

    def load_read_articles(self):
        if os.path.exists(self.read_file):
            try:
                with open(self.read_file, 'r', encoding='utf-8') as f:
                    self.read_articles = set(json.load(f))
            except Exception:
                self.read_articles = set()

    def save_feeds(self):
        saved = {title: data['url'] for title, data in self.feeds.items()}
        try:
            with open(self.feed_file, 'w', encoding='utf-8') as f:
                json.dump(saved, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def save_read_articles(self):
        try:
            with open(self.read_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.read_articles), f)
        except Exception:
            pass

    def update_feed_item(self, title):
        unread_count = self.count_unread_in_feed(title)
        item_text = title
        if unread_count > 0:
            item_text = f"{title} ({unread_count} nouveau{'x' if unread_count > 1 else ''})"

        items = self.feed_list.findItems(title, Qt.MatchFlag.MatchStartsWith)
        if items:
            item = items[0]
            item.setText(item_text)
        else:
            self.feed_list.addItem(item_text)

        font = QFont()
        font.setBold(unread_count > 0)
        if items:
            items[0].setFont(font)
        else:
            new_item = self.feed_list.item(self.feed_list.count() - 1)
            if new_item:
                new_item.setFont(font)

    def count_unread_in_feed(self, title):
        if title not in self.feeds:
            return 0
        count = 0
        for entry in self.feeds[title]['entries']:
            link = entry.get('link', '')
            if link and link not in self.read_articles:
                count += 1
        return count

    def add_feed(self):
        url = self.feed_input.text().strip()
        if not url:
            return
        feed = feedparser.parse(url)
        if hasattr(feed.feed, 'title') and feed.feed.title:
            title = feed.feed.title
            if title not in self.feeds:
                self.feeds[title] = {'url': url, 'entries': feed.entries}
                self.update_feed_item(title)
                self.feed_input.clear()
                self.save_feeds()
            else:
                QMessageBox.information(self, "Info", "Ce flux est déjà ajouté.")
        else:
            QMessageBox.warning(self, "Erreur", "Flux invalide ou inaccessible.")

    def show_feed_context_menu(self, position):
        item = self.feed_list.itemAt(position)
        if not item:
            return

        clean_title = item.text().split(' (')[0]
        title = next((t for t in self.feeds if t == clean_title), None)
        if not title:
            return

        menu = QMenu()
        menu.addAction("Supprimer le flux", lambda: self.delete_feed(title, item))
        menu.addAction("Copier le lien du flux", lambda: self.copy_feed_link(title))
        menu.addAction("Renommer le flux", lambda: self.rename_feed(title))
        menu.addAction("Actualiser le flux", lambda: self.refresh_feed(title))
        menu.addAction("Marquer tous les articles comme \"Lu\"", lambda: self.mark_all_read(title))

        menu.exec(self.feed_list.mapToGlobal(position))

    def show_global_context_menu(self, position):
        menu = QMenu()
        menu.addAction("Configurer l’actualisation automatique...", self.configure_refresh)
        menu.exec(self.mapToGlobal(position))

    def configure_refresh(self):
        current = self.refresh_timer.interval() // 1000
        new_interval, ok = QInputDialog.getInt(
            self, "Actualisation automatique",
            "Intervalle en secondes (30 à 120) :", current, 30, 120, 10)
        if ok:
            self.refresh_timer.start(new_interval * 1000)
            self.settings.setValue("refresh_interval", new_interval)
            QMessageBox.information(self, "Configuration", f"Actualisation toutes les {new_interval} secondes.")

    def refresh_all_feeds(self):
        if not self.feeds:
            return
        for title in list(self.feeds.keys()):
            url = self.feeds[title]['url']
            fresh = feedparser.parse(url)
            if fresh.entries:
                old_count = self.count_unread_in_feed(title)
                self.feeds[title]['entries'] = fresh.entries
                new_count = self.count_unread_in_feed(title)
                if new_count != old_count:
                    self.update_feed_item(title)
                    if self.feed_list.currentItem() and self.feed_list.currentItem().text().startswith(title):
                        self.load_articles(self.feed_list.currentItem())

    def delete_feed(self, title, item):
        if QMessageBox.question(self, "Confirmer", f"Supprimer le flux « {title} » ?") == QMessageBox.StandardButton.Yes:
            del self.feeds[title]
            row = self.feed_list.row(item)
            self.feed_list.takeItem(row)
            self.article_list.clear()
            self.article_view.setHtml("")
            self.save_feeds()

    def copy_feed_link(self, title):
        url = self.feeds[title]['url']
        QApplication.clipboard().setText(url)
        QMessageBox.information(self, "Copié", "Lien du flux copié dans le presse-papiers !")

    def rename_feed(self, title):
        new_name, ok = QInputDialog.getText(self, "Renommer", "Nouveau nom :", text=title)
        if ok and new_name and new_name != title:
            self.feeds[new_name] = self.feeds.pop(title)
            self.update_feed_item(new_name)
            self.save_feeds()

    def refresh_feed(self, title):
        url = self.feeds[title]['url']
        fresh = feedparser.parse(url)
        if fresh.entries:
            self.feeds[title]['entries'] = fresh.entries
        self.load_articles(self.feed_list.currentItem())
        QMessageBox.information(self, "Actualisé", f"Le flux « {title} » a été actualisé.")

    def mark_all_read(self, title):
        for entry in self.feeds[title]['entries']:
            link = entry.get('link', '')
            if link:
                self.read_articles.add(link)
        self.save_read_articles()
        self.update_feed_item(title)
        self.load_articles(self.feed_list.currentItem())
        QMessageBox.information(self, "Marqué lu", f"Tous les articles de « {title} » sont marqués comme lus.")

    def load_articles(self, item):
        if not item:
            return
        clean_title = item.text().split(' (')[0]
        title = next((t for t in self.feeds if t == clean_title), None)
        if not title:
            return

        url = self.feeds[title]['url']
        fresh_feed = feedparser.parse(url)
        if fresh_feed.entries:
            self.feeds[title]['entries'] = fresh_feed.entries

        self.article_list.clear()
        for entry in self.feeds[title]['entries']:
            link = entry.get('link', '')
            title_text = entry.get('title', 'Sans titre')
            self.article_list.addItem(title_text)
            article_item = self.article_list.item(self.article_list.count() - 1)
            if link and link not in self.read_articles:
                article_item.setFont(QFont("", weight=QFont.Weight.Bold))

        self.update_feed_item(title)

    def display_article(self, item):
        feed_item = self.feed_list.currentItem()
        if not feed_item or not item:
            return
        clean_feed_title = feed_item.text().split(' (')[0]
        feed_title = next((t for t in self.feeds if t == clean_feed_title), None)
        if not feed_title:
            return

        entries = self.feeds[feed_title]['entries']
        selected_title = item.text()
        for entry in entries:
            if entry.get('title', '') == selected_title:
                link = entry.get('link', '#')
                if link and link not in self.read_articles:
                    self.read_articles.add(link)
                    self.save_read_articles()
                    item.setFont(QFont())
                    self.update_feed_item(feed_title)

                content = ""
                if 'content' in entry and entry.content:
                    content = entry.content[0].value
                elif 'summary' in entry:
                    content = entry.summary
                elif 'description' in entry:
                    content = entry.description
                else:
                    content = "<p>Contenu non disponible dans le flux.</p>"

                html = f"""
                <html>
                <head>
                    <meta charset="utf-8">
                    <style>
                        body {{ background: #292d3e; color: #bec7cc; font-family: Segoe UI, Arial, sans-serif;
                                padding: 30px; margin: 0; line-height: 1.6; }}
                        img {{ max-width: 100%; height: auto; border-radius: 8px; }}
                        a {{ color: #4DA6FF; }}
                        h1, h2, h3 {{ color: #bec7cc; }}
                        hr {{ border-color: #242839; }}
                    </style>
                </head>
                <body>
                    <h2>{entry.get('title', 'Sans titre')}</h2>
                    <p style="font-size:18px;">
                        <a href="{link}">➜ Lire l'article sur le site original</a>
                    </p>
                    <hr>
                    {content}
                </body>
                </html>
                """
                self.article_view.setHtml(html, QUrl(""))

                class ExternalInterceptor(QWebEngineUrlRequestInterceptor):
                    def interceptRequest(self, info):
                        url = info.requestUrl()
                        if url.scheme() in ("http", "https"):
                            QDesktopServices.openUrl(url)
                            info.block(True)

                self.article_view.page().setUrlRequestInterceptor(ExternalInterceptor())
                break

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.isMaximized():
            self.showNormal()
        super().keyPressEvent(event)

    def closeEvent(self, event):
        self.refresh_timer.stop()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RSSReader()
    window.show()
    sys.exit(app.exec())