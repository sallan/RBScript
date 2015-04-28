(setq gnus-select-method '(nntp "text.giganews.com"))
(setq user-full-name "Steve Allan")

(setq gnus-article-skip-boring t)
(setq gnus-check-new-newsgroups nil)
(setq gnus-asynchronous nil)

;; I've commented out the line below to store sent mail locally
;; instead of on server. It's faster and I rarely use it anyway.
;; (setq gnus-message-archive-group "nnimap+F5:Sent Items")

;; SMTP settings
(setq message-send-mail-function 'smtpmail-send-it
      smtpmail-default-smtp-server "owa.f5.com"
      smtpmail-stream-type  'starttls
      smtpmail-smtp-service 587
      smtpmail-mail-address "sallan@f5.com")
      
(setq message-mail-alias-type 'ecomplete)
      
;; Cache ticked articles so they don't get expired
(setq gnus-use-cache t)

;; Reduce expire time on my mail groups from the default 7 days
(setq nnmail-expiry-wait 2)

;; movement
(setq gnus-summary-goto-unread nil)

;: turn on topic mode
(add-hook 'gnus-group-mode-hook 'gnus-topic-mode)

;; don't read active file on startup
;; (setq gnus-read-active-file 'some)

;; Customize summary format
;; I've resisted spending the time to grok all these format specifiers
;; and instead of stolen these from the web.
;;
;; The default string is: %U%R%z%I%(%[%4L: %-20,20n%]%) %s\n

;; This one is compact and clean
(setq gnus-summary-line-format 
      "%-1R %-1U  %-15,15n | %2,2~(cut 4)o/%2,2~(cut 6)o %2,2~(cut 9)o:%2,2~(cut 11)o | %I%(%0,80s%)\n"
      gnus-summary-same-subject ">>>"
      gnus-summary-mode-line-format "%V: %%b")

