-- weapon_ar15 entries for ox_inventory/data/weapons.lua (this file is not loaded by ox on its own)
-- Do not replace ox_inventory's file with this one: copy the entry under Weapons into ox's Weapons
-- table and the four entries under Components into ox's Components table. Ammo uses ox's
-- existing 'ammo-rifle' (5.56). Item images: copy ../web/images/*.png to ox_inventory/web/images/.
return {
    Weapons = {
        ['WEAPON_AR15'] = {
            label = 'AR-15',
            weight = 3200,
            durability = 0.02,
            ammoname = 'ammo-rifle',
        },
    },

    Components = {
        ['at_ar15_holo'] = {
            label = 'Celownik holograficzny',
            description = 'Do AR-15. Po założeniu przyrządy mechaniczne składają się pod celownikiem.',
            type = 'sight',
            weight = 320,
            client = {
                component = { `COMPONENT_AT_AR15_SCOPE_HOLO` },
                usetime = 2500
            }
        },

        ['at_ar15_grip'] = {
            label = 'Chwyt przedni kątowy',
            description = 'Do AR-15. Kątowy chwyt przedni na szynę M-LOK.',
            type = 'grip',
            weight = 60,
            client = {
                component = { `COMPONENT_AT_AR15_AFGRIP` },
                usetime = 2500
            }
        },

        ['at_ar15_flashlight'] = {
            label = 'Latarka taktyczna',
            description = 'Do AR-15. Latarka na broń montowana z prawej strony łoża.',
            type = 'flashlight',
            weight = 150,
            client = {
                component = { `COMPONENT_AT_AR15_FLSH` },
                usetime = 2500
            }
        },

        ['at_ar15_laser'] = {
            label = 'Laser',
            description = 'Do AR-15. Czerwony laser z lewej strony łoża; włączanie klawiszem J (do zmiany w ustawieniach).',
            type = 'laser',
            weight = 90,
            client = {
                component = { `COMPONENT_AT_AR15_LASER` },
                usetime = 2500
            }
        },
    },
}
