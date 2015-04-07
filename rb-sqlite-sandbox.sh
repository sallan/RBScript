#!/bin/bash
usage="USAGE: $0 domain site-name"
domain=$1
site=$2

if [ -z "$domain" ]; then
    echo Need a domain name.
    echo $usage
    exit 1
fi

if [ -z "$site" ]; then
    echo Need name of site, e.g. 'rb1', 'rb-main', 'foo'.
    echo $usage
    exit 1
fi

webroot="/var/www/$site"

# Stop web service and remove old site if exists
service httpd stop
if [ $? != 0 ]; then
    echo "Failed to stop web server - exiting."
    exit 1
fi

if [ -d $webroot ]; then
    echo "Deleting old $webroot"
    rm -rf $webroot
fi

# Create new site
rb-site install --noinput --domain-name $domain \
                --site-root '/' \
                --media-url 'media/' \
                --db-type 'sqlite3' \
                --db-name "$webroot/data/reviewboard.db" \
                --admin-user 'sallan' \
                --admin-password 'sallan' \
                --admin-email 'me@home.com'\
                --cache-type 'memcached' \
                --cache-info 'localhost:11211' \
                --web-server-type 'apache' \
                --python-loader 'wsgi' \
                --opt-out-support-data \
                $webroot

# Fix permissions
cd $webroot
chown -R apache:apache data logs 
chown -R apache:apache htdocs/media/uploaded htdocs/media/ext htdocs/static/ext
cp -fv  $webroot/conf/apache-wsgi.conf /etc/httpd/conf.d/${site}.conf

# Restart web server
echo "Installation done. Restarting the httpd service."
service httpd start
if [ $? != 0 ]; then
    echo "Problem restarting web server!"
    exit 1
fi
exit 0
