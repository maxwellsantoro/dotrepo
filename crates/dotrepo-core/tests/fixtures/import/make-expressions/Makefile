build := ignored
define template
build:
endef
$(info build: ignored)
ifeq ($(ENABLE),yes)
test:
endif
private define hidden
build:
endef
 ifdef FLAG
test:
 endif
