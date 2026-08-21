def classFactory(iface):
    from .plugin import RnaEtpPlugin

    return RnaEtpPlugin(iface)
