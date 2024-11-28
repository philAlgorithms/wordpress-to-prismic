import os
import xml.etree.ElementTree as ET
from datetime import datetime
import time
from typing import Dict, List, Any, Tuple
import httpx
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import re
import json
import asyncio
from urllib.parse import urlparse, unquote
from pathlib import Path
import requests
load_dotenv()

class WordPressToPrismicMigrator:
    def __init__(self):
        self.repository_name = os.getenv('PRISMIC_REPOSITORY_NAME')
        self.api_token = os.getenv('PRISMIC_ACCESS_TOKEN')
        self.api_key = os.getenv('PRISMIC_MIGRATION_API_KEY')
        self.migration_url = "https://migration.prismic.io/documents"
        self.api_url = f"https://{self.repository_name}.cdn.prismic.io/api/v2"
        self.asset_upload_url = "https://asset-api.prismic.io/assets"
        
    async def get_master_ref(self) -> str:
        """Get the master ref from Prismic API."""
        async with httpx.AsyncClient() as client:
            response = await client.get(self.api_url)
            if response.status_code != 200:
                print(f"Error getting master ref. Status: {response.status_code}")
                print(f"Response: {response.text}")
                return None
                
            try:
                data = response.json()
                master_ref = next(ref['ref'] for ref in data['refs'] if ref['isMasterRef'])
                return master_ref
            except Exception as e:
                print(f"Error parsing master ref response: {str(e)}")
                return None

    async def get_current_posts(self) -> List[Dict[str, Any]]:
        """Fetch all existing posts from Prismic."""
        print("\nFetching current posts from Prismic...")
        
        async with httpx.AsyncClient() as client:
            try:
                # Get the master ref
                master_ref = await self.get_master_ref()
                if not master_ref:
                    print("Could not get master ref")
                    return []
                
                # Query for all posts
                query_url = f"{self.api_url}/documents/search"
                params = {
                    'ref': master_ref,
                    'q': '[[at(document.type,"post")]]'
                }
                
                response = await client.get(query_url, params=params)
                print(f"API Response Status: {response.status_code}")
                print(f"API Response Headers: {dict(response.headers)}")
                
                if response.status_code != 200:
                    print(f"Error fetching posts. Response: {response.text}")
                    return []
                
                try:
                    data = response.json()
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON response: {str(e)}")
                    print(f"Raw response: {response.text[:500]}...")
                    return []
                
                if data.get('results_size', 0) > 0:
                    print(f"\nFound {data['results_size']} existing posts in Prismic:")
                    for post in data['results']:
                        title = post.get('data', {}).get('title', [{}])[0].get('text', 'No title')
                        print(f"- {post['uid']}: {title}")
                    return data['results']
                else:
                    print("No existing posts found in Prismic")
                    return []
                    
            except Exception as e:
                print(f"Error fetching current posts: {str(e)}")
                import traceback
                traceback.print_exc()
                return []

    def parse_wordpress_xml(self, xml_path: str) -> List[Dict[str, Any]]:
        """Parse WordPress XML export file and extract posts."""
        print(f"\nParsing WordPress XML file: {xml_path}")
        
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            namespaces = {
                'content': 'http://purl.org/rss/1.0/modules/content/',
                'wp': 'http://wordpress.org/export/1.2/',
                'excerpt': 'http://wordpress.org/export/1.2/excerpt/',
            }
            
            posts = []
            for item in list(root.findall('.//item'))[2:3]:
                post_type = item.find('wp:post_type', namespaces)
                status = item.find('wp:status', namespaces)
                
                if (post_type is not None and post_type.text == 'post' and 
                    status is not None and status.text == 'publish'):
                    
                    content = item.find('content:encoded', namespaces)
                    title = item.find('title')
                    pub_date = item.find('pubDate')
                    post_name = item.find('wp:post_name', namespaces)
                    
                    post_data = {
                        'title': title.text if title is not None else '',
                        'content': content.text if content is not None else '',
                        'publication_date': pub_date.text if pub_date is not None else '',
                        'uid': post_name.text if post_name is not None else ''
                    }
                    posts.append(post_data)
                    print(f"Found post: {post_data['title']}")
            
            return posts
            
        except Exception as e:
            print(f"Error parsing WordPress XML: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
      
    async def upload_image_asset(self, url: str) -> str|bool:
        headers = {
            'Authorization': f'Bearer {self.api_token}',
            'x-api-key': self.api_key,
            'repository': self.repository_name,
            "Content-Type": "multipart/form-data",
            "Accept": "application/json",
        }
        
        try:
            # Download image using requests
            image_response = requests.get(url)
            if image_response.status_code != 200:
                print(f"Failed to download image. Status code: {image_response.status_code}")
                return False
            
            # Prepare the image for uploading
            files = {
                'file': ('image.jpg', image_response.content, 'image/jpeg')  # Name and MIME type
            }

            # Use httpx to upload the image asynchronously
            async with httpx.AsyncClient() as client:
                try:
                    await asyncio.sleep(2)  # Add rate limiting
                    response = await client.post(
                        self.asset_upload_url,
                        files=files,
                        headers=headers,
                        timeout=30.0
                    )
                    response.raise_for_status()  # Will raise an HTTPError if response is not 2xx

                    if response.status_code == 201:
                        asset_data = response.json()
                        asset_id = asset_data['id']
                        print(f'Uploaded asset ID: {asset_id}')
                        return asset_id
                    else:
                        print(f'Error: {response.status_code} - {response.text}')
                        return False
                except httpx.HTTPError as e:
                    print(f"✗ Failed to upload image {url}: {str(e)}")
                    if hasattr(e.response, 'text'):
                        print(f"Error details: {e.response.text}")
                    
                    if getattr(e.response, 'status_code', None) == 429:
                        wait_time = 10  # Adjust wait time based on your needs
                        print(f"Rate limit hit, waiting {wait_time} seconds...")
                        await asyncio.sleep(wait_time)
                except Exception as e:
                    print(f"✗ Unexpected error while uploading image {url}: {str(e)}")
        except Exception as e:
            print(f"Error fetching image: {str(e)}")
            return False  
    def strip_double_slashes(self, string: str) -> str:
        return string.replace('"\\', '').replace('\\"', '')
    
    async def html_to_prismic_richtext(self, html_content: str) -> List[Dict[str, Any]]:
        """Convert HTML content to Prismic Rich Text format, handling inline captions."""
        if not html_content:
            return []

        try:
            # Regex to capture [caption] blocks, including nested HTML content
            caption_regex = r"\[caption[^\]]*\](.*?)\[/caption\]"

            paragraphs = []
            for paragraph in html_content.split("\n\n"):
                paragraph = paragraph.strip()
                if not paragraph:
                    continue

                # Detect and process captions
                caption_match = re.search(caption_regex, paragraph, re.DOTALL)

                if caption_match:
                    caption_html = caption_match.group(1)  # Entire HTML content inside [caption]
                    soup_caption = BeautifulSoup(caption_html, "html.parser")
                    
                    print(f"{caption_html}")
                    # Extract the image tag
                    image_tag = soup_caption.find("img")
                    if image_tag:
                        image_url = self.strip_double_slashes(image_tag.get("src", ""))
                        image_alt = self.strip_double_slashes(image_tag.get("alt", ""))
                        image_title = self.strip_double_slashes(image_tag.get("title", ""))
                        caption_text = soup_caption.get_text(strip=True).replace(
                            image_tag.get_text(strip=True), ""
                        ).strip()
                        
                        image_id = await self.upload_image_asset(image_url)
                        
                        if(image_id):
                            # Add caption and inline image
                            paragraphs.append({
                                "id": self.upload_image_asset(image_url),
                                "type": "image",
                                "url": image_url,
                                "alt": image_alt,
                                "title": image_title,
                                "caption": caption_text
                            })
                    continue  # Skip to the next paragraph

                # Regular text paragraph
                paragraphs.append({
                    "type": "paragraph",
                    "text": paragraph,
                    "spans": [],
                    "direction": "ltr"
                })

            return paragraphs
        except Exception as e:
            print(f"Error converting HTML to rich text: {str(e)}")
            return []
        
    async def create_prismic_document(self, post: Dict[str, Any]) -> Dict[str, Any]:
        """Transform WordPress post into Prismic document format."""
        try:
            uid = post['uid'] or re.sub(r'[^a-z0-9-]', '', post['title'].lower().replace(' ', '-'))
            uid = uid[:150]  # Ensure UID isn't too long
            
            try:
                pub_date = datetime.strptime(
                    post['publication_date'],
                    '%a, %d %b %Y %H:%M:%S %z'
                ).strftime('%Y-%m-%d')
            except:
                pub_date = datetime.now().strftime('%Y-%m-%d')
            
            return {
                'title': post['title'],
                'uid': uid,
                'type': 'post',
                'lang': 'en-us',
                'data': {
                    'title': [{
                        'type': 'paragraph',
                        'text': post['title'],
                        'spans': [],
                        'direction': 'ltr'
                    }],
                    'published_date': pub_date,
                    'body': await self.html_to_prismic_richtext(post['content']),
                    # 'author': {
                    #     'link_type': 'Any',
                    #     'text': 'AWP Network'
                    # },
                    'slices': []
                }
            }
        except Exception as e:
            print(f"Error creating Prismic document: {str(e)}")
            return None

    async def migrate_to_prismic(self, posts: List[Dict[str, Any]], existing_posts: List[Dict[str, Any]]) -> None:
        """Migrate posts to Prismic via the Migration API."""
        headers = {
            'Authorization': f'Bearer {self.api_token}',
            'repository': self.repository_name,
            'x-api-key': self.api_key,
            'Content-Type': 'application/json'
        }
        
        existing_uids = {post['uid'] for post in existing_posts}
        
        async with httpx.AsyncClient() as client:
            for i, post in enumerate(posts, 1):
                prismic_doc = await self.create_prismic_document(post)
                if not prismic_doc:
                    print(f"\nSkipping post {i}/{len(posts)}: {post['title']} (error creating document)")
                    continue
                
                if prismic_doc['uid'] in existing_uids:
                    print(f"\nSkipping post {i}/{len(posts)}: {post['title']} (already exists)")
                    continue
                
                print(f"\nProcessing post {i}/{len(posts)}: {post['title']}")
                print(f"Document to be sent:\n{json.dumps(prismic_doc, indent=2)}")
                
                try:
                    await asyncio.sleep(2)  # Rate limiting
                    
                    response = await client.post(
                        self.migration_url,
                        json=prismic_doc,
                        headers=headers,
                        timeout=30.0
                    )
                    response.raise_for_status()
                    print(f"✓ Successfully migrated: {post['title']}")
                    print(f"Response: {response.text}")
                    
                    # Wait extra time after successful migration
                    await asyncio.sleep(3)
                    
                except httpx.HTTPError as e:
                    print(f"✗ Failed to migrate {post['title']}: {str(e)}")
                    if hasattr(e.response, 'text'):
                        print(f"Error details: {e.response.text}")
                    
                    if getattr(e.response, 'status_code', None) == 429:
                        wait_time = 10
                        print(f"Rate limit hit, waiting {wait_time} seconds...")
                        await asyncio.sleep(wait_time)
                except Exception as e:
                    print(f"✗ Unexpected error while migrating {post['title']}: {str(e)}")

async def main():
    # Print environment variables (without revealing sensitive data)
    print("Environment variables:")
    print(f"Repository name: {os.getenv('PRISMIC_REPOSITORY_NAME')}")
    print(f"API token length: {len(os.getenv('PRISMIC_ACCESS_TOKEN') or '')}")
    print(f"Migration key length: {len(os.getenv('PRISMIC_MIGRATION_API_KEY') or '')}")
    
    migrator = WordPressToPrismicMigrator()
    
    # First, fetch current posts
    existing_posts = await migrator.get_current_posts()
    
    # Then parse WordPress XML
    posts = migrator.parse_wordpress_xml('wordpress-export.xml')
    
    if not posts:
        print("No posts found to migrate. Exiting.")
        return
        
    print(f"\nFound {len(posts)} posts to migrate")
    
    proceed = input("Do you want to proceed with the migration? (y/n): ")
    if proceed.lower() != 'y':
        print("Migration cancelled")
        return
    
    await migrator.migrate_to_prismic(posts, existing_posts)

if __name__ == "__main__":
    asyncio.run(main())