import _ from 'intl'
import ActionButton from 'action-button'
import Component from 'base-component'
import Icon from 'icon'
import React from 'react'
import { checkXoaHlUpdate, getXoaHlUpdateProgress, getXoaHlUpdateStatus, getXoaHlVersion, startXoaHlUpdate } from 'xo'

// ===================================================================

export default class XoaHlUpdates extends Component {
  componentWillMount() {
    this.state = {
      version: undefined,
      checking: false,
      updateAvailable: false,
      latestVersion: undefined,
      updating: false,
      log: [],
    }
    getXoaHlVersion().then(version => this.setState({ version }))
  }

  _checkForUpdate = async () => {
    this.setState({ checking: true })
    await checkXoaHlUpdate()
    const { updateAvailable, latestVersion } = await getXoaHlUpdateStatus()
    this.setState({ checking: false, updateAvailable, latestVersion })
  }

  _startUpdate = async () => {
    this.setState({ updating: true })
    await startXoaHlUpdate()
    const { log } = await getXoaHlUpdateProgress()
    this.setState({ updating: false, log })
  }

  render() {
    const { version, checking, updateAvailable, latestVersion, log } = this.state

    return (
      <div>
        <p>
          {_('xoaHlInstalledVersion')} {version === undefined ? '-' : String(version)}
        </p>
        <p>
          {updateAvailable ? (
            <span>
              {_('xoaHlUpdateAvailable')} {latestVersion}
            </span>
          ) : (
            _('xoaHlUpToDate')
          )}
        </p>
        <ActionButton btnStyle='info' handler={this._checkForUpdate} icon='refresh' pending={checking}>
          {_('xoaHlCheckForUpdate')}
        </ActionButton>{' '}
        <ActionButton
          btnStyle='success'
          disabled={!updateAvailable}
          handler={this._startUpdate}
          icon='upgrade'
        >
          {_('xoaHlStartUpdate')}
        </ActionButton>
        {log.length > 0 && (
          <div>
            <hr />
            <pre className='overflow-auto' style={{ maxHeight: '20em' }}>
              {log.join('\n')}
            </pre>
          </div>
        )}
      </div>
    )
  }
}
