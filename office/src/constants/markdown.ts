// Documents are read-only text: no form controls, images, embeds or styles; Alpine-looking attributes
// (x-*, @*, :*) are not in DOMPurify's allow list and so never survive.
const SANITIZE_OPTIONS = {
  FORBID_TAGS: ['form', 'input', 'button', 'select', 'textarea', 'img', 'style', 'iframe', 'object', 'embed'],
  FORBID_ATTR: ['style'],
};

const SUMMARY_HEADING = '## Summary';

const MARKDOWN_EXTENSION = '.md';

const PATH_SEPARATOR = '/';

const SECTION_HEADING_PREFIX = '## ';

const ANCHOR_TAG_NAME = 'A';

const HREF_ATTRIBUTE = 'href';

const NOT_FOUND_INDEX = -1;

export {
  SANITIZE_OPTIONS,
  SUMMARY_HEADING,
  MARKDOWN_EXTENSION,
  PATH_SEPARATOR,
  SECTION_HEADING_PREFIX,
  ANCHOR_TAG_NAME,
  HREF_ATTRIBUTE,
  NOT_FOUND_INDEX,
};
