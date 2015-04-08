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


if grep -q apache /etc/passwd; then
    web_owner='apache'
    web_conf_dir='/etc/httpd/conf.d'
fi
if grep -q www-data /etc/passwd; then
    web_owner='www-data'
    web_conf_dir='/etc/apache2/sites-available'
fi
if [ -z "$web_owner" ]; then
    echo Unable to determine owner of web server
    exit 1
fi

webroot="/var/www/$site"

# Stop web service and remove old site if exists
service httpd status > /dev/null 2>&1
if [ $? = 0 ]; then
    service_name='httpd'
else
    service_name='apache2'
fi

service $service_name stop
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
chown -R $web_owner:$web_owner data logs 
chown -R $web_owner:$web_owner htdocs/media/uploaded htdocs/media/ext htdocs/static/ext
cp -fv  $webroot/conf/apache-wsgi.conf $web_conf_dir/${site}.conf

# Restart web server
echo "Installation done. Restarting the httpd service."
service $service_name start
if [ $? != 0 ]; then
    echo "Problem restarting web server!"
    exit 1
fi
exit 0
