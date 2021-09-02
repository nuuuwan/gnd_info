python3 src/gnd_info/scrape.py

git checkout data
git pull origin data

cp /tmp/gnd_info.tsv ./
git add .
git commit -m "scrape_and_upload_data.sh"
git push origin data

git checkout main
