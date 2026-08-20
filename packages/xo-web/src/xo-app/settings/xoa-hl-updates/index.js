import _ from 'intl'
import ActionButton from 'action-button'
import Component from 'base-component'
import React from 'react'
import { checkXoaHlUpdate, getXoaHlUpdateProgress, getXoaHlUpdateStatus, startXoaHlUpdate } from 'xo'

// ===================================================================

// The page content is a flex column, so the log can claim the leftover height.
const CONTAINER_STYLE = {
  display: 'flex',
  flexDirection: 'column',
  height: '100%',
}

const NO_SHRINK_STYLE = {
  flexShrink: 0,
}

// Capped so a long package list still leaves room for the log.
const STATUS_STYLE = {
  flexShrink: 0,
  maxHeight: '40%',
  overflowY: 'auto',
}

const LOG_STYLE = {
  display: 'flex',
  flexDirection: 'column',
  flex: 1,
  minHeight: 0,
}

// minHeight lets the pre shrink below its content and scroll on its own.
const LOG_PRE_STYLE = {
  flex: 1,
  minHeight: 0,
  marginBottom: 0,
}

export default class XoaHlUpdates extends Component {
  constructor(props) {
    super(props)
    this.state = {
      checking: false,
      updateAvailable: false,
      packages: [],
      updating: false,
      log: [],
    }
  }

  _checkForUpdate = async () => {
    // Drop the previous run's log: it does not describe the result being fetched.
    this.setState({ checking: true, log: [] })
    await checkXoaHlUpdate()
    const { updateAvailable, packages } = await getXoaHlUpdateStatus()
    this.setState({ checking: false, updateAvailable, packages })
  }

  _startUpdate = async () => {
    this.setState({ updating: true })
    await startXoaHlUpdate()
    const { log } = await getXoaHlUpdateProgress()
    this.setState({ updating: false, log })
  }

  render() {
    const { checking, updateAvailable, packages, log } = this.state

    return (
      <div style={CONTAINER_STYLE}>
        <div style={NO_SHRINK_STYLE}>
          <ActionButton btnStyle='info' handler={this._checkForUpdate} icon='refresh' pending={checking}>
            {_('xoaHlCheckForUpdate')}
          </ActionButton>{' '}
          <ActionButton btnStyle='success' disabled={!updateAvailable} handler={this._startUpdate} icon='upgrade'>
            {_('xoaHlStartUpdate')}
          </ActionButton>
        </div>
        <div style={STATUS_STYLE}>
          {updateAvailable && packages.length > 0 ? (
            <div>
              <p>{_('xoaHlPackagesAvailable')}</p>
              <table className='table'>
                <thead>
                  <tr>
                    <th>{_('xoaHlPackageName')}</th>
                    <th>{_('xoaHlPackageVersion')}</th>
                  </tr>
                </thead>
                <tbody>
                  {packages.map(({ name, version }) => (
                    <tr key={name}>
                      <td>{name}</td>
                      <td>{version}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p>{_('xoaHlUpToDate')}</p>
          )}
        </div>
        {log.length > 0 && (
          <div style={LOG_STYLE}>
            <hr style={NO_SHRINK_STYLE} />
            <pre className='overflow-auto' style={LOG_PRE_STYLE}>
              {log.join('\n')}
            </pre>
          </div>
        )}
      </div>
    )
  }
}
