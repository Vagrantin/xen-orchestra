import forEach from 'lodash/forEach.js'

const PARAM_RE = /^([^=]+)=([^]*)$/
export function parseParameters(args) {
  const params = {}
  forEach(args, function (arg) {
    let matches
    if (!(matches = arg.match(PARAM_RE))) {
      throw new Error('invalid arg: ' + arg)
    }
    const name = matches[1]
    let value = matches[2]

    if (value.startsWith('json:')) {
      // already typed, `json:"true"` must stay a string
      params[name] = JSON.parse(value.slice(5))
      return
    }

    if (name === '@') {
      params['@'] = value
      return
    }

    if (value === 'true') {
      value = true
    } else if (value === 'false') {
      value = false
    }

    params[name] = value
  })

  return params
}
