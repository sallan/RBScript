#!/usr/bin/perl
use strict;
use warnings;
use Data::Dumper;
use Getopt::Long;
use IPC::Open2;
use HTTP::Cookies;
use HTTP::Request;
use HTTP::Request::Common;
use HTTP::Response;
use LWP::UserAgent;

# TODO: Fix this crap. I want ua, rr and all this other nonsense to be light objects.
my $ua;

#===========================================================================
# Handrolled JSON. I hope to get rid of this.
#===========================================================================
my $json_indent_step = 2;

sub json_encode_scalar(\$);
sub json_encode_array($ \@);
sub json_encode_hash($ \%);

sub json_encode_scalar(\$) {
    my $v = $_[0];
    if ( $$v eq 'true' || $$v eq 'false' || $$v eq 'null' ) {
        return $$v;
    }
    if ( $$v =~ /^(-)?[0-9]+$/ ) {
        return $$v;
    }
    my $enc;
    my $n;
    my %json_escape_ctrl
        = ( "\b" => 'b', "\f" => 'f', "\n" => 'n', "\r" => 'r', "\t" => 't' );
    $enc .= "\"";
    for ( $n = 0; $n < length($$v); ++$n ) {
        my $c = substr( $$v, $n, 1 );
        if ( $c eq '\\' || $c eq '"' || $c eq '/' ) {
            $enc .= "\\$c";
        }
        elsif ( defined( $json_escape_ctrl{$c} ) ) {
            $enc .= "\\" . $json_escape_ctrl{$c};
        }
        else {
            $enc .= $c;
        }
    }
    $enc .= "\"";
    return $enc;
}

sub json_encode_array($ \@) {
    my $indent    = $_[0];
    my $data      = $_[1];
    my $datacount = scalar( @{$data} );
    my $enc;

    my $n = 0;
    while ( $n < $datacount ) {
        $enc .= " " x $indent;
        my $v = $data->[$n];
        my $r = ref($v);
        if ( $r eq '' ) {
            $v = \$data->[$n];
            $r = ref($v);
        }
        if ( $r eq 'SCALAR' ) {
            $enc .= json_encode_scalar($$v);
        }
        elsif ( $r eq 'ARRAY' ) {
            $enc .= "[\n";
            $enc .= json_encode_array( $indent + $json_indent_step, @$v );
        }
        elsif ( $r eq 'HASH' ) {
            $enc .= "{\n";
            $enc .= json_encode_hash( $indent + $json_indent_step, %$v );
        }
        else {
            die("json_encode: cannot encode type=$r\n");
        }
        ++$n;
        if ( $n < $datacount ) {
            $enc .= ",";
        }
        $enc .= "\n";
    }
    $indent -= $json_indent_step;
    $enc .= " " x $indent . "]";
    return $enc;
}

sub json_encode_hash($ \%) {
    my $indent    = $_[0];
    my $data      = $_[1];
    my $datacount = scalar( keys %{$data} );
    my $enc;

    my $n = 0;
    foreach my $key ( keys %$data ) {
        $enc .= " " x $indent;
        $enc .= "\"$key\" : ";
        my $v = $data->{$key};
        my $r = ref($v);
        if ( $r eq '' ) {
            $v = \$data->{$key};
            $r = ref($v);
        }
        if ( $r eq 'SCALAR' ) {
            $enc .= json_encode_scalar($$v);
        }
        elsif ( $r eq 'ARRAY' ) {
            $enc .= "[\n";
            $enc .= json_encode_array( $indent + $json_indent_step, @$v );
        }
        elsif ( $r eq 'HASH' ) {
            $enc .= "{\n";
            $enc .= json_encode_hash( $indent + $json_indent_step, %$v );
        }
        else {
            die("json_encode: cannot encode type=$r\n");
        }
        ++$n;
        if ( $n < $datacount ) {
            $enc .= ",";
        }
        $enc .= "\n";
    }
    $indent -= $json_indent_step;
    $enc .= " " x $indent . "}";
    return $enc;
}

sub json_encode(\%) {
    my $enc;
    $enc = "{\n";
    $enc .= json_encode_hash( $json_indent_step, %{ $_[0] } );
    $enc .= "\n";
    return $enc;
}

sub json_next_token(\$ \$) {
    my $enc    = $_[0];
    my $pos    = $_[1];
    my $enclen = length($$enc);

    while ( $$pos < $enclen && substr( $$enc, $$pos, 1 ) =~ /\s/ ) {
        ++$$pos;
    }
    if ( $$pos >= $enclen ) {
        warn("json_next_token: EOI\n");
        return '';
    }

    my $json_toks     = "{}:[],";
    my $json_numbegin = "-0123456789";
    my $json_numbody  = "0123456789.Ee";
    my %json_escape_ctrl
        = ( 'b' => "\b", 'f' => "\f", 'n' => "\n", 'r' => "\r", 't' => "\t" );

    my $tok = substr( $$enc, $$pos++, 1 );
    if ( index( $json_toks, $tok ) < 0 ) {
        if ( index( $json_numbegin, $tok ) >= 0 ) {
            while ( index( $json_numbody, substr( $$enc, $$pos, 1 ) ) >= 0 ) {
                $tok .= substr( $$enc, $$pos++, 1 );
            }
        }
        elsif ( $tok eq '"' ) {
            $tok = '';
            my $c;
            while ( ( $c = substr( $$enc, $$pos, 1 ) ) ne '"' ) {
                if ( $c eq '\\' ) {
                    ++$$pos;
                    $c = substr( $$enc, $$pos, 1 );
                    if ( $c eq '"' || $c eq '\\' || $c eq '/' ) {

                        # no-op
                    }
                    elsif ( defined( $json_escape_ctrl{$c} ) ) {
                        $c = $json_escape_ctrl{$c};
                    }
                    elsif ( $c eq 'u' ) {
                        my $h4 = substr( $$enc, $$pos + 1, 4 );
                        if ( $h4 !~ /[[:xdigit:]]{4}/i ) {
                            warn(
                                "json_next_token: unknown sequence \\u$h4\n");
                            $h4 = "003f";    # '?'
                        }
                        $c = chr( hex("0x$h4") );
                        $$pos += 4;
                    }
                    else {
                        warn("json_next_token: unknown sequence \\$c\n");
                    }
                }
                $tok .= $c;
                ++$$pos;
            }
            ++$$pos;
        }
        else {
            while ( $$pos < $enclen && substr( $$enc, $$pos, 1 ) =~ /\w/ ) {
                $tok .= substr( $$enc, $$pos++, 1 );
            }
            if ( $tok ne 'true' && $tok ne 'false' && $tok ne 'null' ) {
                warn("json_next_token: unknown token $tok\n");
            }
        }
    }
    verbose( 4, "json_next_token: tok=$tok\n" );
    return $tok;
}

sub json_decode_array(\$ \$);
sub json_decode_hash(\$ \$);

sub json_decode_array(\$ \$) {
    my $enc = $_[0];
    my $pos = $_[1];
    my $tok;
    my @data;

    $tok = json_next_token( $$enc, $$pos );
    while ( $tok ne ']' ) {
        if ( $tok eq '[' ) {
            my @a = json_decode_array( $$enc, $$pos );
            push( @data, \@a );
        }
        elsif ( $tok eq '{' ) {
            my %h = json_decode_hash( $$enc, $$pos );
            push( @data, \%h );
        }
        else {
            push( @data, $tok );
        }
        $tok = json_next_token( $$enc, $$pos );
        if ( $tok ne ',' && $tok ne ']' ) {
            die("json_decode_array: expected comma or close bracket\n");
        }
        if ( $tok eq ',' ) {
            $tok = json_next_token( $$enc, $$pos );
        }
    }
    return @data;
}

sub json_decode_hash(\$ \$) {
    my $enc = $_[0];
    my $pos = $_[1];
    my $tok;
    my %data;

    $tok = json_next_token( $$enc, $$pos );
    while ( $tok ne '}' ) {
        my $key = $tok;
        $tok = json_next_token( $$enc, $$pos );
        if ( $tok ne ':' ) {
            die("json_decode_hash: expected colon\n");
        }
        $tok = json_next_token( $$enc, $$pos );
        if ( $tok eq '[' ) {
            my @a = json_decode_array( $$enc, $$pos );
            $data{$key} = \@a;
        }
        elsif ( $tok eq '{' ) {
            my %h = json_decode_hash( $$enc, $$pos );
            $data{$key} = \%h;
        }
        else {
            $data{$key} = $tok;
        }
        $tok = json_next_token( $$enc, $$pos );
        if ( $tok ne ',' && $tok ne '}' ) {
            die("json_decode_hash: expected comma or close brace\n");
        }
        if ( $tok eq ',' ) {
            $tok = json_next_token( $$enc, $$pos );
        }
    }
    return %data;
}

sub json_decode(\$) {
    my $enc = $_[0];
    my $pos = 0;
    my %data;
    my $tok;
    $tok = json_next_token( $$enc, $pos );
    if ( $tok ne '{' ) {
        die("json_decode: expected open brace\n");
    }
    %data = json_decode_hash( $$enc, $pos );
    return %data;
}

# End of JSON stuff

#===============================================================================
# HTTP stuff
#===============================================================================
my %custom_error_messages = (
    103 => "
############################################################
#
# ERROR: You are not logged in to reviewboard
#
# Please log in using your OLYMPUS credentials with this command:
# $0 login
#
############################################################

",
);

sub new_lwp {
    my $lwp_version = shift;
    return 0 unless $lwp_version;

# Every version of LWP I've seen begins with a digit. So any version that doesn't
# start with a digit we'll treat as old. Easy enough to fix later if this causes
# problems. Given that, we'll just pull off the leading digit and compare it to
# the version we consider new.
    my $is_new = 0;
    if ( $lwp_version =~ /^(\d+)/ ) {
        $is_new = ( $1 >= 6 );
    }
    return $is_new;
}

my $verbose_level = 1;

sub verbose {
    print STDERR $_[1] if ( $verbose_level >= $_[0] );
}

sub http_transaction {
    my $request = shift;
    verbose( 4, ">>>\n" . $request->as_string() . ">>>\n" );
    my $response = $ua->request($request);
    verbose( 4, "<<<\n" . $response->as_string() . "<<<\n" );
    return $response;
}

sub rb_exec_request {
    my $request = shift;

    my $response = http_transaction($request);
    if ( !$response->is_success() ) {
        my $errcode = $response->code();
        my $errmsg  = $response->message();
        die("Error: server returned error $errcode ($errmsg)\n");
    }
    my $dc   = $response->content();
    my %data = json_decode($dc);
    if ( !defined( $data{'stat'} ) ) {
        die("Error: no stat returned from request\n");
    }
    if ( $data{'stat'} ne 'ok' ) {

        my $msg
            = "Error: server request failed...\n"
            . "\turi="
            . $request->uri() . "\n"
            . "\tstat="
            . $data{'stat'} . "\n"
            . "\tcode="
            . $data{'err'}{'code'} . "\n"
            . "\tmsg="
            . $data{'err'}{'msg'} . "\n"
            . "Full server response:\n"
            . json_encode(%data);

        if ( exists( $custom_error_messages{ $data{err}->{code} } ) ) {
            $msg .= "\n" . $custom_error_messages{ $data{err}->{code} };
        }

        die($msg);
    }
    verbose( 3,
              ">>>\n"
            . $request->method() . " "
            . $request->uri() . "\n" . ">>>\n" . "<<<\n"
            . json_encode(%data)
            . "<<<\n" );
    return %data;
}

# End HTTP stuff

sub api_get {
    my $uri     = shift;
    my $request = HTTP::Request::Common::GET($uri);
    return rb_exec_request($request);
}

sub apt_put {
    # TODO: This is not done.
    my ( $uri, $fields ) = @_;
    my $request = HTTP::Request::Common::PUT($uri);
    return rb_exec_request($request);
}

#sub get_api {
#    my $request = HTTP::Request::Common::GET("http://giles/api/");
#    my %data = rb_exec_request($request);
#}

sub get_review_requests {
    my $uri = "http://giles/api/review-requests/";
    return api_get($uri);
}

sub get_review_request {
    my $rid  = shift;
    my $uri  = "http://giles/api/review-requests/$rid/";
    my %data = api_get($uri);
    return $data{'review_request'};
}

sub get_review_draft {
    my $rid                = shift;
    my $review_request_ref = get_review_request($rid);
    my $uri = $review_request_ref->{'links'}->{'draft'}->{'href'};
    return api_get($uri);
}

#==================================================================================
# main
#==================================================================================

# Newer versions of LWP::UserAgent are stricter about checking ssl
# certificates, and ours fails. To get around this we use the new
# option to turn off hostname verification, but only on the newer
# versions.
if ( new_lwp($LWP::UserAgent::VERSION) ) {
    $ua = LWP::UserAgent->new( ssl_opts => { verify_hostname => 0 } );
}
else {
    $ua = LWP::UserAgent->new();
}

# TODO: quick hack on prefs.   Neeeds work
my %prefs = ( cookiefile => '/Users/sallan/.buffyluvscookies', );

$ua->cookie_jar(
    HTTP::Cookies->new(
        file         => $prefs{'cookiefile'},
        hide_cookie2 => 1
    )
);

my $server_url = "http://giles";
my $rid        = 73;

#my %review_requests = get_review_requests();
#print Dumper(%review_requests)

#my %review_request = get_review_request($rid);
#print Dumper(%review_request)

# my %api = get_api();
# print Dumper($api{'links'});

# TODO: Before you can make any progress, you need to understand authentication.
#print Dumper( get_review_draft($rid) );
print Dumper( get_review_request($rid) );

